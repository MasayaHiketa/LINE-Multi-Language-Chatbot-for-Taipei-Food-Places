# -*- coding: utf-8 -*-
# line_bot.py

import time
import os
import re
import logging
import sys
import urllib.parse
from urllib.parse import (
    urlsplit, urlunsplit, parse_qs, parse_qsl, quote, urlencode
)

import requests
from fastapi import FastAPI, Request, HTTPException, Response
from linebot import LineBotApi, WebhookParser
from linebot.models import FlexSendMessage
from linebot.exceptions import InvalidSignatureError

from ramen_qa import answer_ramen
from geo_utils import extract_location_from_text  # 地名→座標

# =========================
# ロギング
# =========================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("line_app")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(h)
logger.setLevel(LOG_LEVEL)

# =========================
# FastAPI / 環境変数
# =========================
app = FastAPI()

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_TOKEN  = os.getenv("LINE_CHANNEL_TOKEN")
# Google Maps は GOOGLE_MAPS_API_KEY 優先、無ければ GOOGLE_API_KEY
GOOGLE_API_KEY  = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_API_KEY")

logger.info(f"🌐 PUBLIC_BASE_URL = {PUBLIC_BASE_URL or '(empty)'}")
logger.info(f"🔑 GOOGLE_API_KEY set = {bool(GOOGLE_API_KEY)}")

if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_TOKEN:
    raise RuntimeError("LINE_CHANNEL_SECRET と LINE_CHANNEL_TOKEN を設定してください")

line_bot_api = LineBotApi(LINE_CHANNEL_TOKEN)
parser = WebhookParser(LINE_CHANNEL_SECRET)

# =========================
# ラベル正規化
# =========================
_NORMALIZE_LABEL = {
    # 店名 / Name
    "店名": "店名", "Name": "店名", "名稱": "店名", "名前": "店名",
    # 評價 / Rating / 評価
    "評價": "評價", "Rating": "評價", "評判": "評價", "評価": "評價",
    # 地址 / Address / 住所
    "地址": "地址", "Address": "地址", "住所": "地址",
    # 推薦 / Recommendations / おすすめ
    "推薦": "推薦", "Recommendation": "推薦", "Recommendations": "推薦",
    "Recommended": "推薦", "おすすめ": "推薦",
    # 特色 / Features / 特徴
    "特色": "特色", "Features": "特色", "Feature": "特色", "特徴": "特色",
    # 營業時間 / Opening Hours / 営業時間
    "營業時間": "營業時間", "Opening Hours": "營業時間",
    "Hours of Operation": "營業時間", "Business Hours": "營業時間", "営業時間": "營業時間",
    # Link / 連結 / リンク / URL
    "Link": "Link", "連結": "Link", "URL": "Link", "リンク": "Link",
}

def parse_response_to_dict(text: str) -> dict:
    """LLMの「キー：値」行から辞書を作る（全角/半角コロン対応）"""
    raw = {}
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue

        if "：" in s:
            key, val = s.split("：", 1)
        elif ":" in s:
            key, val = s.split(":", 1)
        else:
            continue

        key = key.strip()
        val = val.strip()

        std_key = _NORMALIZE_LABEL.get(key, key)

        # 末尾の句読点や括弧の剥がしは Link のみ実施
        if std_key == "Link":
            val = val.rstrip("。．。、）」)]】』>")

        raw.setdefault(std_key, val)

    return raw

# =========================
# 言語判定 & ラベル
# =========================
def detect_locale(s: str) -> str:
    if re.search(r'[\u3040-\u30FF]', s):  # ひらがな・カタカナ
        return "ja"
    ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in s)
    if ascii_letters / max(1, len(s)) > 0.5 and not re.search(r'[\u4E00-\u9FFF]', s):
        return "en"
    return "zh"

LABELS = {
    "zh": {"rating": "評價", "recommend": "推薦", "features": "特色", "hours": "營業時間", "map": "查看地圖"},
    "ja": {"rating": "評価", "recommend": "おすすめ", "features": "特徴", "hours": "営業時間", "map": "地図を開く"},
    "en": {"rating": "Rating", "recommend": "Recommendations", "features": "Features", "hours": "Hours", "map": "Open Map"},
}
# =========================
# =========================
def _parse_rating(rating_str: str):
    """'4.3（320件）' '4.5 (1,234 reviews)' などから
    score(float) と count(str) を抜く。count は数字だけ。"""
    if not rating_str:
        return None, None

    # スコア（最初に出る数値）
    score = None
    m = re.search(r'(\d+(?:\.\d+)?)', rating_str)
    if m:
        try:
            score = float(m.group(1))
        except ValueError:
            score = None

    # 件数（カッコ内 or 単体）
    count = None
    m2 = re.search(
        r'[\(（]\s*([0-9][0-9,]*)\s*(?:件|則|条|reviews?|ratings?|人の評価)?\s*[\)）]',
        rating_str,
        re.IGNORECASE
    )
    if m2:
        count = m2.group(1).replace(",", "")
    else:
        m3 = re.search(
            r'([0-9][0-9,]*)\s*(?:件|則|条|reviews?|ratings?)',
            rating_str,
            re.IGNORECASE
        )
        if m3:
            count = m3.group(1).replace(",", "")

    return score, count

# =========================
# URL 正規化 & フォールバック
# =========================
def _is_valid_uri_for_line(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not (url.startswith("https://") or url.startswith("http://")):
        return False
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("https", "http"):
            return False
        if not parts.netloc:
            return False
        if any(ch.isspace() for ch in url):
            return False
        if len(url) > 1000:
            return False
    except Exception:
        return False
    return True

def _normalize_link(raw: str) -> str:
    """文中やMarkdownから https URL を抽出→安全に整形。失敗なら空文字。"""
    if not raw:
        return ""
    s = raw.strip()

    # Markdown [text](URL)
    m = re.search(r"\((https?://[^\s)]+)\)", s)
    if m:
        s = m.group(1)

    # <URL> の囲いを剥がす
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1].strip()

    # 生URL拾い
    if not s.startswith("http"):
        m2 = re.search(r"(https?://[^\s]+)", s)
        if m2:
            s = m2.group(1)

    # 末尾の全角句読点/括弧などを落とす & 空白除去
    s = s.rstrip("。．。、）」)]】』>").strip()
    s = re.sub(r"\s+", "", s)

    # 再エンコード
    try:
        parts = urlsplit(s)
        if not parts.scheme or not parts.netloc:
            return ""
        safe_path = quote(parts.path or "/", safe="/%._-~")
        q_pairs = parse_qsl(parts.query, keep_blank_values=True)
        safe_query = urlencode(q_pairs, doseq=True)
        safe_frag = quote(parts.fragment or "", safe="%-._~")
        s = urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, safe_frag))
    except Exception:
        return ""

    return s if _is_valid_uri_for_line(s) else ""

def _build_maps_query_url(name: str = "", address: str = "") -> str:
    q_parts = [p.strip() for p in [name, address] if p and p.strip()]
    if not q_parts:
        return ""
    q = quote(" ".join(q_parts), safe="")
    url = f"https://www.google.com/maps/search/?api=1&query={q}"
    return url if _is_valid_uri_for_line(url) else ""

# =========================
# テキスト整形
# =========================
def _extract_hours_compact(val: str) -> str:
    """営業時間の 12:00 - 21:00 などを抽出して簡潔表記"""
    val_norm = re.sub(r"[—–−~〜-]", "-", val)
    times = re.findall(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", val_norm)
    return "; ".join(times) if times else val

# =========================
# Photo helper
# =========================
def _extract_ref_from_url(url: str) -> str:
    """既存のGoogle画像URLから photo_reference を抜く"""
    if not url:
        return ""
    try:
        qs = parse_qs(urlsplit(url).query)
        return qs.get("photo_reference", [""])[0]
    except Exception:
        return ""

# =========================
# /photo プロキシ (Places Photo API)
# =========================
@app.get("/photo/{ref:path}")
def photo_proxy(ref: str):
    """
    Google Places Photo を安全にプロキシする。
    - /photo/<photo_reference>.jpg 形式に対応（拡張子は捨てる）
    - ref に URL 丸ごとも来たら photo_reference を抽出
    """
    try:
        logger.info(f"📸 /photo hit ref(raw)='{ref}'")
        orig_ref = ref

        # 拡張子剥がし
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            if ref.lower().endswith(ext):
                ref = ref[: -len(ext)]
                break

        # URL 丸ごと → photo_reference 抽出
        if ref.startswith("http"):
            qs = parse_qs(urlsplit(ref).query)
            ref = qs.get("photo_reference", [None])[0] or ref

        # 形チェック
        if not ref or len(ref) < 10:
            logger.warning(f"/photo invalid ref: orig='{orig_ref}' parsed='{ref}'")
            return Response(status_code=204)

        if not GOOGLE_API_KEY:
            logger.error("GOOGLE_API_KEY is not set")
            return Response(status_code=204)

        google_url = (
            "https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth=800&photo_reference={ref}&key={GOOGLE_API_KEY}"
        )
        logger.debug(f"/photo fetch -> {google_url.replace(GOOGLE_API_KEY, '***')}")

        r = requests.get(google_url, timeout=15, allow_redirects=True)
        ctype = r.headers.get("Content-Type", "")
        logger.debug(f"/photo resp status={r.status_code} ctype='{ctype}' bytes={len(r.content) if r.ok else 0}")

        if r.status_code != 200 or not ctype.startswith("image/"):
            body_head = r.text[:120] if hasattr(r, "text") else ""
            logger.warning(f"/photo non-image or error: status={r.status_code} ctype='{ctype}' body_head={body_head!r}")
            return Response(status_code=204)

        return Response(
            content=r.content,
            media_type=ctype or "image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        logger.exception(f"/photo fatal error: {e}")
        return Response(status_code=204)

# =========================
# Flex Message 生成
# =========================
def build_ramen_flex(data: dict, photo_url: str = "", locale: str = "zh") -> dict:
    labels = LABELS.get(locale, LABELS["zh"])

    # 本文
    body_contents = []

    name = data.get("店名")
    if name:
        body_contents.append({
            "type": "text",
            "text": name,
            "weight": "bold",
            "size": "xl",
            "wrap": True
        })

    rating_val = data.get("評價")
    if rating_val:
        score, count = _parse_rating(rating_val)
        if score is not None:
            # 5個の★/☆（四捨五入、0〜5にクリップ）
            filled = max(0, min(5, int(round(score))))
            stars = "★" * filled + "☆" * (5 - filled)

            body_contents.append({
                "type": "box",
                "layout": "baseline",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": stars,
                        "size": "sm",
                        "color": "#ffcc00",
                        "wrap": False,
                        "flex": 0
                    },
                    {
                        "type": "text",
                        "text": f"{score:.1f}",  # ★の真横に数値
                        "size": "sm",
                        "color": "#333333",
                        "margin": "sm",
                        "wrap": False,
                        "flex": 0
                    },
                    *([{
                        "type": "text",
                        "text": f"({count})",   # 評価数が取れたら表示
                        "size": "sm",
                        "color": "#666666",
                        "margin": "sm",
                        "wrap": False,
                        "flex": 0
                    }] if count else [])
                ]
            })
        else:
            # パースできなかったときの素朴なフォールバック
            body_contents.append({
                "type": "text",
                "text": rating_val,
                "size": "sm",
                "color": "#666666",
                "margin": "xs",
                "wrap": True
            })



    fields = [
        ("地址", labels.get("address", "地址")),
        ("推薦", labels["recommend"]),
        ("特色", labels["features"]),
        ("營業時間", labels["hours"]),
    ]
    for key, label_title in fields:
        val = data.get(key)
        if not val:
            continue
        if key == "營業時間":
            val = _extract_hours_compact(val)

        body_contents.append({
            "type": "box",
            "layout": "baseline",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": f"{label_title}:",
                    "weight": "bold",
                    "color": "#333333",
                    "size": "sm",
                    "flex": 3,
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": val,
                    "size": "sm",
                    "color": "#666666",
                    "flex": 9,
                    "wrap": True,
                    **({"maxLines": 3} if key == "特色" else {})
                }
            ]
        })

    link = _normalize_link(data.get("Link", "")) or _build_maps_query_url(
        name=name or "", address=data.get("地址", "")
    )

    # Flex本体（画像は hero に置く）
    flex = {
        "type": "bubble",
        **({
            "hero": {
                "type": "image",
                "url": photo_url,
                "size": "full",
                "aspectMode": "cover",
                "aspectRatio": "20:13"
            }
        } if photo_url else {}),
        "body": {"type": "box", "layout": "vertical", "contents": body_contents},
    }

    if link:
        flex["footer"] = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [{
                "type": "button",
                "style": "link",
                "height": "sm",
                "action": {"type": "uri", "label": labels["map"], "uri": link}
            }],
            "flex": 0
        }

    return flex

# =========================
# Webhook
# =========================
@app.post("/callback")
async def callback(request: Request):
    logger.debug("✅ /callback にリクエストが届きました")

    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()

    try:
        events = parser.parse(body.decode(), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if event.type == "message" and event.message.type == "text":
            user_text = event.message.text
            locale = detect_locale(user_text)

            # 地名→座標→metadata_filter
            lat, lng = extract_location_from_text(user_text, GOOGLE_API_KEY)
            metadata_filter = {"location": {"lat": lat, "lng": lng}} if (lat is not None and lng is not None) else None

            # RAG検索（古いシグネチャ互換）
            try:
                raw_replies = answer_ramen(user_text, metadata_filters=metadata_filter)
            except TypeError:
                raw_replies = answer_ramen(user_text)

            bubbles = []
            for result in (raw_replies or [])[:10]:
                data = parse_response_to_dict(result.get("text", ""))
                if not data:
                    continue

                # photo_reference を優先的に使う。なければ photo_url から抽出
                ref = result.get("photo_ref", "") or _extract_ref_from_url(result.get("photo_url", ""))
                if ref:
                    if PUBLIC_BASE_URL:
                        photo_url = f"{PUBLIC_BASE_URL}/photo/{ref}.jpg?v={int(time.time())}"
                    else:
                        # ローカルURL（http→https 補正 & キャッシュバスター）
                        tmp = str(request.url_for("photo_proxy", ref=f"{ref}.jpg"))
                        if tmp.startswith("http://"):
                            tmp = "https://" + tmp[len("http://"):]
                        photo_url = tmp + ("&" if "?" in tmp else "?") + f"v={int(time.time())}"
                else:
                    photo_url = ""

                logger.debug(f"🧩 photo_url for Flex: {photo_url}")

                bubble = build_ramen_flex(data, photo_url=photo_url, locale=locale)
                bubbles.append(bubble)

            if not bubbles:
                return "OK"

            flex_carousel = {"type": "carousel", "contents": bubbles}
            message = FlexSendMessage(alt_text="餐廳資訊", contents=flex_carousel)
            line_bot_api.reply_message(event.reply_token, message)

    return "OK"
