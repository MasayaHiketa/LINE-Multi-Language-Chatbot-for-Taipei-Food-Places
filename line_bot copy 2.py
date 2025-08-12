# #line_bot.py


# import os
# import re
# from fastapi import FastAPI, Request, HTTPException
# from linebot import LineBotApi, WebhookParser
# from linebot.models import FlexSendMessage
# from linebot.exceptions import InvalidSignatureError
# from ramen_qa import answer_ramen
# # ← 追加（最上部）
# from geo_utils import extract_location_from_text

# app = FastAPI()

# LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
# LINE_CHANNEL_TOKEN  = os.getenv("LINE_CHANNEL_TOKEN")
# GOOGLE_API_KEY      = os.getenv("GOOGLE_API_KEY")
# if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_TOKEN:
#     raise RuntimeError("LINE_CHANNEL_SECRET と LINE_CHANNEL_TOKEN を設定してください")

# line_bot_api = LineBotApi(LINE_CHANNEL_TOKEN)
# parser = WebhookParser(LINE_CHANNEL_SECRET)


# def parse_response_to_dict(text: str) -> dict:
#     raw = {}
#     for line in text.splitlines():
#         line = line.strip()
#         if "：" in line:
#             key, val = line.split("：", 1)
#         elif ":" in line:
#             key, val = line.split(":", 1)
#         else:
#             continue
#         raw[key.strip()] = val.strip()

#     # ラベル正規化（英→中）
#     normalize = {
#         "店名": "店名",
#         "Name": "店名",

#         "評價": "評價",
#         "Rating": "評價",

#         "地址": "地址",
#         "Address": "地址",

#         "推薦": "推薦",
#         "Recommendation": "推薦",
#         "Recommendations": "推薦",

#         "特色": "特色",
#         "Features": "特色",

#         "營業時間": "營業時間",
#         "Opening Hours": "營業時間",
#         "Hours of Operation": "營業時間",

#         "Link": "Link",
#         "連結": "Link",
#         "URL": "Link",
#     }

#     data = {}
#     for k, v in raw.items():
#         data[normalize.get(k, k)] = v
#     return data

# # ➊ 追加：URL正規化ヘルパー
# def _normalize_link(raw: str) -> str:
#     if not raw:
#         return ""
#     s = raw.strip()

#     # Markdown [text](https://...) → https://...
#     m = re.search(r"\((https?://[^\s)]+)\)", s)
#     if m:
#         s = m.group(1)

#     # もし生の https://... が入っていればそれを拾う
#     if not s.startswith("http"):
#         m2 = re.search(r"(https?://[^\s]+)", s)
#         if m2:
#             s = m2.group(1)
#         else:
#             return ""  # http/https 以外は捨てる（LINEで弾かれる）

#     # 空白はエンコード
#     s = s.replace(" ", "%20")

#     # 末尾の全角/句読点/カッコ閉じなどを落とす
#     s = s.rstrip("。）」)]）")

#     return s



# def build_ramen_flex(data: dict, photo_url: str = "") -> dict:
#     body_contents = []

#     if photo_url:
#         body_contents.append({
#             "type": "image",
#             "url": photo_url,
#             "size": "full",
#             "aspectMode": "cover",
#             "aspectRatio": "20:13",
#             "gravity": "top"
#         })

#     name = data.get("店名")
#     if name:
#         body_contents.append({
#             "type": "text",
#             "text": name,
#             "weight": "bold",
#             "size": "xl",
#             "wrap": True
#         })

#     rating_val = data.get("評價")
#     if rating_val:
#         body_contents.append({
#             "type": "text",
#             "text": f"評價：{rating_val}",
#             "size": "sm",
#             "color": "#ff9900",
#             "margin": "xs",
#             "wrap": True
#         })

#     for key, prefix in [
#         ("地址", ""),
#         ("捷運站", "捷運站："),
#         ("推薦", "推薦："),
#         ("特色", "特色："),
#         ("營業時間", "營業時間："),
#     ]:
#         val = data.get(key)
#         if not val:
#             continue
#         if key == "營業時間":
#             times = re.findall(r'\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}', val)
#             val = "; ".join(times) if times else val

#         block = {
#             "type": "text",
#             "text": f"{prefix}{val}" if prefix else val,
#             "size": "sm",
#             "color": "#666666",
#             "margin": "xs",
#             "wrap": True
#         }
#         if key == "特色":
#             block["maxLines"] = 3
#         body_contents.append(block)

#     # ✅ フッターの地図URLを正規化
#     link_raw = data.get("Link", "")
#     link = _normalize_link(link_raw)

#     flex = {
#         "type": "bubble",
#         "body": {"type": "box", "layout": "vertical", "contents": body_contents},
#     }

#     if link:
#         flex["footer"] = {
#             "type": "box",
#             "layout": "vertical",
#             "spacing": "sm",
#             "contents": [{
#                 "type": "button",
#                 "style": "link",
#                 "height": "sm",
#                 "action": {"type": "uri", "label": "查看地圖", "uri": link}
#             }],
#             "flex": 0
#         }

#     return flex




# from linebot.models import CarouselContainer

# @app.post("/callback")
# async def callback(request: Request):
#     signature = request.headers.get("X-Line-Signature", "")
#     body = await request.body()

#     try:
#         events = parser.parse(body.decode(), signature)
#     except InvalidSignatureError:
#         raise HTTPException(status_code=400, detail="Invalid signature")

#     for event in events:
#         if event.type == "message" and event.message.type == "text":
#             user_text = event.message.text

#             # ✨ 地名から座標抽出して metadata_filter に変換
#             lat, lng = extract_location_from_text(user_text, GOOGLE_API_KEY)
#             metadata_filter = None
#             if lat is not None and lng is not None:
#                 metadata_filter = {"location": {"lat": lat, "lng": lng}}

#             # ⛳ 地名を反映した状態で検索
#             raw_replies = answer_ramen(user_text, metadata_filters=metadata_filter)

#             bubbles = []
#             for result in raw_replies[:10]:
#                 data = parse_response_to_dict(result["text"])
#                 photo_url = result.get("photo_url", "")
#                 bubble = build_ramen_flex(data, photo_url=photo_url)
#                 bubbles.append(bubble)

#             if not bubbles:
#                 return "OK"

#             flex_carousel = {
#                 "type": "carousel",
#                 "contents": bubbles
#             }

#             message = FlexSendMessage(
#                 alt_text="餐廳資訊（複数）",
#                 contents=flex_carousel
#             )
#             line_bot_api.reply_message(event.reply_token, message)

#     return "OK"
#line_bot.py

import os
import re
import urllib.parse
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.models import FlexSendMessage
from linebot.exceptions import InvalidSignatureError
from ramen_qa import answer_ramen
from geo_utils import extract_location_from_text  # 地名→座標

app = FastAPI()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_TOKEN  = os.getenv("LINE_CHANNEL_TOKEN")
GOOGLE_API_KEY      = os.getenv("GOOGLE_API_KEY")
if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_TOKEN:
    raise RuntimeError("LINE_CHANNEL_SECRET と LINE_CHANNEL_TOKEN を設定してください")

line_bot_api = LineBotApi(LINE_CHANNEL_TOKEN)
parser = WebhookParser(LINE_CHANNEL_SECRET)

# ============ 1) 多言語→標準キー（繁中）へ正規化 ============

# 入力の可能性があるラベル: ZH/EN/JA を網羅
_NORMALIZE_LABEL = {
    # 店名 / Name
    "店名": "店名",
    "Name": "店名",
    "名稱": "店名",
    "名前": "店名",

    # 評價 / Rating / 評価
    "評價": "評價",
    "Rating": "評價",
    "評判": "評價",
    "評価": "評價",

    # 地址 / Address / 住所
    "地址": "地址",
    "Address": "地址",
    "住所": "地址",

    # 推薦 / Recommendations / おすすめ
    "推薦": "推薦",
    "Recommendation": "推薦",
    "Recommendations": "推薦",
    "Recommended": "推薦",
    "おすすめ": "推薦",

    # 特色 / Features / 特徴
    "特色": "特色",
    "Features": "特色",
    "Feature": "特色",
    "特徴": "特色",

    # 營業時間 / Opening Hours / 営業時間
    "營業時間": "營業時間",
    "Opening Hours": "營業時間",
    "Hours of Operation": "營業時間",
    "Business Hours": "營業時間",
    "営業時間": "營業時間",

    # Link / 連結 / リンク / URL
    "Link": "Link",
    "連結": "Link",
    "URL": "Link",
    "リンク": "Link",
}

# 受け取りテキストから「キー：値」を抜く（全角/半角コロン両対応）
def parse_response_to_dict(text: str) -> dict:
    raw = {}
    # 許容するセパレータ（全角コロン、半角コロン、全角スペースを含む）
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue

        # まず "：" 全角で分割
        if "：" in s:
            key, val = s.split("：", 1)
        elif ":" in s:
            key, val = s.split(":", 1)
        else:
            # 「Rating 4.5」みたいなケースは無視
            continue

        key = key.strip()
        val = val.strip()

        # 末尾の装飾（。）」)]） など）を落とす
        val = val.rstrip("。）」)]）")

        # 正規化
        std_key = _NORMALIZE_LABEL.get(key, key)
        # 既に同じキーが入っている場合は「最初に来たものを優先」
        raw.setdefault(std_key, val)

    return raw

# ============ 2) URL 正規化 & フォールバック生成 ============

def _normalize_link(raw: str) -> str:
    """Link欄からhttps系URLを抽出・整形。なければ空文字。"""
    if not raw:
        return ""
    s = raw.strip()

    # Markdown [text](https://...) → https://...
    m = re.search(r"\((https?://[^\s)]+)\)", s)
    if m:
        s = m.group(1)

    # 「http(s)://...」が素で入っている場合を拾う
    if not s.startswith("http"):
        m2 = re.search(r"(https?://[^\s]+)", s)
        if m2:
            s = m2.group(1)
        else:
            return ""

    # 空白は%20
    s = s.replace(" ", "%20")
    # 末尾の全角/句読点/カッコ閉じなどを落とす
    s = s.rstrip("。）」)]）")
    return s

def _build_maps_query_url(name: str = "", address: str = "") -> str:
    """Linkが無いとき用に Google Maps 検索URLを生成。"""
    q_parts = [p for p in [name, address] if p]
    if not q_parts:
        return ""
    q = urllib.parse.quote(" ".join(q_parts))
    return f"https://www.google.com/maps/search/?api=1&query={q}"

# ============ 3) Flex Message 生成 ============

def _extract_hours_compact(val: str) -> str:
    """
    営業時間の文字列から時間レンジ（12:00 – 21:00 など）を抜いて圧縮表示。
    '–' '—' '-' '〜' いずれも許容。
    """
    # ダッシュ類を統一
    val_norm = re.sub(r"[—–−~〜-]", "-", val)
    # 12:00 - 21:00 を収集（複数可）
    times = re.findall(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", val_norm)
    return "; ".join(times) if times else val

def build_ramen_flex(data: dict, photo_url: str = "") -> dict:
    body_contents = []

    if photo_url:
        body_contents.append({
            "type": "image",
            "url": photo_url,
            "size": "full",
            "aspectMode": "cover",
            "aspectRatio": "20:13",
            "gravity": "top"
        })

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
        body_contents.append({
            "type": "text",
            "text": f"評價：{rating_val}",
            "size": "sm",
            "color": "#ff9900",
            "margin": "xs",
            "wrap": True
        })

    # 本文列（順序固定）
    for key, prefix in [
        ("地址", ""),
        ("推薦", "推薦："),
        ("特色", "特色："),
        ("營業時間", "營業時間："),
    ]:
        val = data.get(key)
        if not val:
            continue

        if key == "營業時間":
            val = _extract_hours_compact(val)

        block = {
            "type": "text",
            "text": f"{prefix}{val}" if prefix else val,
            "size": "sm",
            "color": "#666666",
            "margin": "xs",
            "wrap": True
        }
        if key == "特色":
            block["maxLines"] = 3  # 長すぎる対策
        body_contents.append(block)

    # フッターの地図URL（Link優先→無ければ店名/住所から生成）
    link = _normalize_link(data.get("Link", ""))
    if not link:
        link = _build_maps_query_url(name=name or "", address=data.get("地址", ""))

    flex = {
        "type": "bubble",
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
                "action": {"type": "uri", "label": "查看地圖", "uri": link}
            }],
            "flex": 0
        }

    return flex

# ============ 4) Webhook ============

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()

    try:
        events = parser.parse(body.decode(), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if event.type == "message" and event.message.type == "text":
            user_text = event.message.text

            # 地名→座標→metadata_filter
            lat, lng = extract_location_from_text(user_text, GOOGLE_API_KEY)
            metadata_filter = None
            if lat is not None and lng is not None:
                metadata_filter = {"location": {"lat": lat, "lng": lng}}

            # RAG検索
            raw_replies = answer_ramen(user_text, metadata_filters=metadata_filter)

            bubbles = []
            for result in raw_replies[:10]:
                data = parse_response_to_dict(result.get("text", ""))
                if not data:  # 何も取れなければスキップ
                    continue
                photo_url = result.get("photo_url", "")
                bubble = build_ramen_flex(data, photo_url=photo_url)
                bubbles.append(bubble)

            if not bubbles:
                return "OK"

            flex_carousel = {"type": "carousel", "contents": bubbles}
            message = FlexSendMessage(alt_text="餐廳資訊", contents=flex_carousel)
            line_bot_api.reply_message(event.reply_token, message)

    return "OK"
line_bot.py
-*- coding: utf-8 -*-
import time
import os
import re
import urllib.parse
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.models import FlexSendMessage
from linebot.exceptions import InvalidSignatureError
from ramen_qa import answer_ramen
from geo_utils import extract_location_from_text  # 地名→座標
import logging, sys

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("line_app")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(h)
logger.setLevel(LOG_LEVEL)
from urllib.parse import urlsplit, parse_qs  # ← parse_qs 必須


app = FastAPI()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_TOKEN  = os.getenv("LINE_CHANNEL_TOKEN")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
GOOGLE_API_KEY  = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_API_KEY")

logger.info(f"🌐 PUBLIC_BASE_URL = {PUBLIC_BASE_URL or '(empty)'}")
logger.info(f"🔑 GOOGLE_API_KEY set = {bool(GOOGLE_API_KEY)}")

if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_TOKEN:
    raise RuntimeError("LINE_CHANNEL_SECRET と LINE_CHANNEL_TOKEN を設定してください")

line_bot_api = LineBotApi(LINE_CHANNEL_TOKEN)
parser = WebhookParser(LINE_CHANNEL_SECRET)

import requests
from fastapi import Response

import os
import logging

logger = logging.getLogger("line_app")

def _extract_ref_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        qs = parse_qs(urlsplit(url).query)
        return qs.get("photo_reference", [""])[0]
    except Exception:
        return ""
    
@app.get("/photo/{ref:path}")
def photo_proxy(ref: str):
    try:
        logger.info(f"📸 /photo hit ref(raw)='{ref}'")
        orig_ref = ref

        # 1) .jpg/.png を剥がす
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            if ref.lower().endswith(ext):
                ref = ref[: -len(ext)]
                break

        # 2) URL 丸ごと来た場合は photo_reference 抜く
        if ref.startswith("http"):
            qs = parse_qs(urlsplit(ref).query)
            ref = qs.get("photo_reference", [None])[0] or ref

        # 3) 形が怪しければ 204
        if not ref or len(ref) < 10:
            logger.warning(f"/photo invalid ref: orig='{orig_ref}' parsed='{ref}'")
            return Response(status_code=204)

        # 4) Google Places Photo 叩く（リダイレクト追従）
        google_key = os.getenv("GOOGLE_API_KEY")
        if not google_key:
            logger.error("GOOGLE_API_KEY is not set")
            return Response(status_code=204)

        google_url = (
            "https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth=800&photo_reference={ref}&key={google_key}"
        )
        logger.debug(f"/photo fetch -> {google_url.replace(google_key, '***')}")

        r = requests.get(google_url, timeout=15, allow_redirects=True)
        ctype = r.headers.get("Content-Type", "")
        logger.debug(f"/photo resp status={r.status_code} ctype='{ctype}' bytes={len(r.content) if r.ok else 0}")

        if r.status_code != 200 or not ctype.startswith("image/"):
            # エラーボディは短く
            body_head = r.text[:120] if hasattr(r, "text") else ""
            logger.warning(f"/photo non-image or error: status={r.status_code} ctype='{ctype}' body_head={body_head!r}")
            return Response(status_code=204)

        # 5) 成功
        return Response(
            content=r.content,
            media_type=ctype or "image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    except Exception as e:
        logger.exception(f"/photo fatal error: {e}")
        return Response(status_code=204)
@app.get("/photo/{ref:path}")
def photo_proxy(ref: str):
    orig_ref = ref
    logger.debug(f"📸 /photo hit: orig='{orig_ref}'")
    ...
    logger.debug(f"/photo fetch -> {safe_url}")
    ...
    logger.debug(f"/photo resp status={r.status_code} ctype='{ctype}' bytes={len(r.content) if r.ok else 0}")
    # .jpg/.png 拡張子を許容
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if ref.lower().endswith(ext):
            ref = ref[: -len(ext)]
            break

    # URL 丸ごとの場合は photo_reference を抽出
    if ref.startswith("http"):
        qs = parse_qs(urlsplit(ref).query)
        ref = qs.get("photo_reference", [None])[0] or ref

    if not ref or len(ref) < 10:
        logger.warning(f"/photo invalid ref: orig='{orig_ref}' parsed='{ref}'")
        return Response(status_code=204)

    google_url = (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photo_reference={ref}&key={GOOGLE_API_KEY}"
    )
    safe_url = google_url.replace(GOOGLE_API_KEY or "", "***")
    logger.debug(f"/photo fetch -> {safe_url}")

    try:
        r = requests.get(google_url, timeout=12, allow_redirects=True)
    except Exception as e:
        logger.exception(f"/photo request error: {e}")
        return Response(status_code=204)

    ctype = r.headers.get("Content-Type", "")
    logger.debug(f"/photo resp status={r.status_code} ctype='{ctype}' bytes={len(r.content) if r.ok else 0}")

    # Places Photo が失敗すると 4xx + JSON/HTML（非 image/*）になりがち
    if r.status_code != 200 or not ctype.startswith("image/"):
        logger.warning(f"/photo non-image or error: status={r.status_code} ctype='{ctype}' body_head={r.text[:120]!r}")
        return Response(status_code=204)

    return Response(
        content=r.content,
        media_type=ctype or "image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
    logger.warning(f"/photo non-image or error: status={r.status_code} ctype='{ctype}' body_head={r.text[:120]!r}")

@app.get("/photo/{ref:path}")
def photo_proxy(ref: str):
    # 1) 末尾の拡張子を剥がす（/photo/XXXX.jpg を許容）
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if ref.lower().endswith(ext):
            ref = ref[: -len(ext)]
            break

    # 2) ref が長いURLの可能性（旧実装からの流用など）
    if ref.startswith("http"):
        qs = parse_qs(urlsplit(ref).query)
        ref = qs.get("photo_reference", [None])[0] or ref

    # 3) photo_reference っぽくない場合は 204
    if not ref or len(ref) < 10:
        return Response(status_code=204)

    google_url = (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photo_reference={ref}&key={GOOGLE_API_KEY}"
    )
    r = requests.get(google_url, timeout=12, allow_redirects=True)

    # 失敗 or 画像じゃない
    ctype = r.headers.get("Content-Type", "")
    if r.status_code != 200 or "image" not in ctype:
        return Response(status_code=204)

    return Response(
        content=r.content,
        media_type=ctype or "image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
from urllib.parse import urlsplit, parse_qs
import requests
from fastapi import Response

@app.get("/photo/{ref:path}")
def photo_proxy(ref: str):
    orig_ref = ref
    # .jpg/.png拡張子を許容
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if ref.lower().endswith(ext):
            ref = ref[: -len(ext)]
            break
    # URL丸ごと来た場合は photo_reference 抜き
    if ref.startswith("http"):
        qs = parse_qs(urlsplit(ref).query)
        ref = qs.get("photo_reference", [None])[0] or ref

    if not ref or len(ref) < 10:
        logger.warning(f"/photo invalid ref: orig='{orig_ref}' parsed='{ref}'")
        return Response(status_code=204)

    google_url = (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photo_reference={ref}&key={GOOGLE_API_KEY}"
    )
    safe_google_url = google_url.replace(GOOGLE_API_KEY or "", "***")
    logger.debug(f"/photo fetch: ref='{ref}' url='{safe_google_url}'")

    try:
        r = requests.get(google_url, timeout=12, allow_redirects=True)
    except Exception as e:
        logger.exception(f"/photo request error: {e}")
        return Response(status_code=204)

    ctype = r.headers.get("Content-Type", "")
    logger.debug(f"/photo resp: status={r.status_code} ctype='{ctype}' bytes={len(r.content) if r.ok else 0}")

    if r.status_code != 200 or "image" not in ctype:
        logger.warning(f"/photo non-image or error: status={r.status_code} ctype='{ctype}'")
        return Response(status_code=204)

    return Response(content=r.content, media_type=ctype or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


=========================
多言語→標準キー（繁中）へ正規化
=========================
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

        # ★ 末尾の句読点やカッコ落としは Link だけに限定
        if std_key == "Link":
            val = val.rstrip("。．。、）」)]】』>")

        raw.setdefault(std_key, val)

    return raw


# =========================
# 言語判定（超軽量）
# =========================
def detect_locale(s: str) -> str:
    # ひらがな・カタカナがあれば日本語
    if re.search(r'[\u3040-\u30FF]', s):
        return "ja"
    # ASCII英字の比率が高く、CJKを含まなければ英語
    ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in s)
    if ascii_letters / max(1, len(s)) > 0.5 and not re.search(r'[\u4E00-\u9FFF]', s):
        return "en"
    # 既定は繁体字
    return "zh"

LABELS = {
    "zh": {
        "rating": "評價",
        "recommend": "推薦",
        "features": "特色",
        "hours": "營業時間",
        "map": "查看地圖",
    },
    "ja": {
        "rating": "評価",
        "recommend": "おすすめ",
        "features": "特徴",
        "hours": "営業時間",
        "map": "地図を開く",
    },
    "en": {
        "rating": "Rating",
        "recommend": "Recommendations",
        "features": "Features",
        "hours": "Hours",
        "map": "Open Map",
    },
}

# =========================
# URL 正規化 & フォールバック
# =========================
import string
from urllib.parse import urlsplit, urlunsplit, quote, urlencode, parse_qsl

# --- LINE用の厳格バリデータ ---
def _is_valid_uri_for_line(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    # LINEは http/https 推奨。実質 https を要求するケースが多い
    if not (url.startswith("https://") or url.startswith("http://")):
        return False
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("https", "http"):
            return False
        if not parts.netloc:
            return False
        # 制御文字や空白（含：全角スペース）を拒否
        if any(ch.isspace() for ch in url):
            return False
        # 全角句読点などは事前に除去しているはずだが、残っていたらNG
        bad_trailers = "。）」)]』】】〉》"
        if url[-1] in bad_trailers:
            return False
        # 長さ制限（念のため）
        if len(url) > 1000:
            return False
    except Exception:
        return False
    return True

# --- 正規化＆再エンコード ---
def _normalize_link(raw: str) -> str:
    """LLMのLink欄をLINE許容のURIへ。ダメなら空文字。"""
    if not raw:
        return ""
    s = raw.strip()

    # Markdown [text](URL) → URL
    m = re.search(r"\((https?://[^\s)]+)\)", s)
    if m:
        s = m.group(1)

    # <https://...> のような括りを剥がす
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1].strip()

    # 生URLを拾う（文中のhttps://...）
    if not s.startswith("http"):
        m2 = re.search(r"(https?://[^\s]+)", s)
        if m2:
            s = m2.group(1)

    # 末尾の全角/句読点/カッコ閉じなどを落とす
    s = s.rstrip("。．。、）」)]】』>")

    # 全角スペース等の空白を除去
    s = re.sub(r"\s+", "", s)

    # 再パースして path / query を適切にエンコードし直す
    try:
        parts = urlsplit(s)
        if not parts.scheme or not parts.netloc:
            return ""
        safe_path   = quote(parts.path or "/", safe="/%._-~")
        # queryをkey-valueに分解→再エンコード
        q_pairs = parse_qsl(parts.query, keep_blank_values=True)
        safe_query = urlencode(q_pairs, doseq=True)
        safe_frag  = quote(parts.fragment or "", safe="%-._~")
        s = urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, safe_frag))
    except Exception:
        return ""

    return s if _is_valid_uri_for_line(s) else ""

# --- Google Maps 検索URL生成（安全版） ---
def _build_maps_query_url(name: str = "", address: str = "") -> str:
    q_parts = [p.strip() for p in [name, address] if p and p.strip()]
    if not q_parts:
        return ""
    # クエリは quote_plus ではなく quote で空白→%20（LINE互換性高め）
    q = quote(" ".join(q_parts), safe="")
    url = f"https://www.google.com/maps/search/?api=1&query={q}"
    return url if _is_valid_uri_for_line(url) else ""

# =========================
# 営業時間の短縮整形
# =========================
def _extract_hours_compact(val: str) -> str:
    """
    営業時間の文字列から 12:00 - 21:00 のような時間範囲を抽出しセミコロン連結。
    '–' '—' '−' '-' '〜' をすべて '-' に正規化。
    """
    val_norm = re.sub(r"[—–−~〜-]", "-", val)
    times = re.findall(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", val_norm)
    return "; ".join(times) if times else val

# =========================
# Flex Message 生成
# =========================
# def build_ramen_flex(data: dict, photo_url: str = "", locale: str = "zh") -> dict:
#     labels = LABELS.get(locale, LABELS["zh"])
#     body_contents = []

#     if photo_url:
#         body_contents.append({
#             "type": "image",
#             "url": photo_url,
#             "size": "full",
#             "aspectMode": "cover",
#             "aspectRatio": "20:13",
#             "gravity": "top"
#         })

#     name = data.get("店名")
#     if name:
#         body_contents.append({
#             "type": "text",
#             "text": name,
#             "weight": "bold",
#             "size": "xl",
#             "wrap": True
#         })

#     rating_val = data.get("評價")
#     if rating_val:
#         # 星＋数値を全部黄色で
#         body_contents.append({
#             "type": "text",
#             "text": f"{labels['rating']}: {rating_val}",
#             "size": "sm",
#             "color": "#ffcc00",  # 黄色
#             "margin": "xs",
#             "wrap": True
#         })


#     fields = [
#         ("地址", labels.get("address", "地址")),
#         ("推薦", labels['recommend']),
#         ("特色", labels['features']),
#         ("營業時間", labels['hours']),
#     ]
#     for key, label_title in fields:
#         val = data.get(key)
#         if not val:
#             continue
#         if key == "營業時間":
#             val = _extract_hours_compact(val)

#         # ラベルと値を分けて強調
#         body_contents.append({
#             "type": "box",
#             "layout": "baseline",
#             "spacing": "sm",
#             "contents": [
#                 {
#                     "type": "text",
#                     "text": f"{label_title}:",  # タイトル
#                     "weight": "bold",
#                     "color": "#333333",  # 濃いグレー
#                     "size": "sm",
#                     "flex": 3,
#                     "wrap": True
#                 },
#                 {
#                     "type": "text",
#                     "text": val,  # 値
#                     "size": "sm",
#                     "color": "#666666",
#                     "flex": 9,
#                     "wrap": True,
#                     **({"maxLines": 3} if key == "特色" else {})
#                 }
#             ]
#         })


#     link = _normalize_link(data.get("Link", "")) or _build_maps_query_url(
#         name=name or "", address=data.get("地址", "")
#     )

#     flex = {
#         "type": "bubble",
#         "body": {"type": "box", "layout": "vertical", "contents": body_contents},
#     }

#     if link:
#         flex["footer"] = {
#             "type": "box",
#             "layout": "vertical",
#             "spacing": "sm",
#             "contents": [{
#                 "type": "button",
#                 "style": "link",
#                 "height": "sm",
#                 "action": {"type": "uri", "label": labels["map"], "uri": link}
#             }],
#             "flex": 0
#         }

#     return flex

def build_ramen_flex(data: dict, photo_url: str = "", locale: str = "zh") -> dict:
    labels = LABELS.get(locale, LABELS["zh"])

    # ===== 本文 =====
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

    # 「★4.7」の詰め表記（数字だけ抽出して付与）
    rating_val = data.get("評價")
    if rating_val:
        import re
        m = re.search(r"\d+(?:\.\d+)?", rating_val)
        rating_num = m.group(0) if m else rating_val
        body_contents.append({
            "type": "text",
            "text": f"★{rating_num}",   # ← 星の後ろにスペースなし
            "size": "sm",
            "color": "#ffcc00",
            "margin": "xs",
            "wrap": True
        })

    # ラベル強調（住所/おすすめ/特徴/営業時間）
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

    # 地図リンク（Link優先→なければ店名/住所から生成）
    link = _normalize_link(data.get("Link", "")) or _build_maps_query_url(
        name=name or "", address=data.get("地址", "")
    )

    # ===== Flex本体 =====
    flex = {
        "type": "bubble",
        # 画像は hero に置く（LINE が必ず先に取りに来る）
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

            # RAG検索
            try:
                raw_replies = answer_ramen(user_text, metadata_filters=metadata_filter)
            except TypeError:
                # 古いシグネチャ互換（metadata_filters未対応版）
                raw_replies = answer_ramen(user_text)

            bubbles = []
            # for result in (raw_replies or [])[:10]:
            #     data = parse_response_to_dict(result.get("text", ""))
            #     if not data:
            #         continue
            #     photo_url = result.get("photo_url", "")
            #     bubbles.append(build_ramen_flex(data, photo_url=photo_url, locale=locale))
            # for result in (raw_replies or [])[:10]:
            #     data = parse_response_to_dict(result.get("text", ""))

            #     photo_ref = result.get("photo_ref")  # ← これ、ちゃんと参照値を持ってますか？
            #     if photo_ref:
            #         # あなたの公開HTTPSドメイン（ngrokでも可）。必ず https://
            #         photo_url = f"https://YOUR_DOMAIN/photo/{photo_ref}.jpg"
            #     else:
            #         photo_url = ""


            #     bubble = build_ramen_flex(data, photo_url=photo_url, locale=locale)
            #     bubbles.append(bubble)
            for result in (raw_replies or [])[:10]:
                data = parse_response_to_dict(result.get("text", ""))

                ref = result.get("photo_ref", "")
                logger.debug(f"🖼 photo_ref from result: {ref}")

                if not ref:
                    ref = _extract_ref_from_url(result.get("photo_url", ""))
                    logger.debug(f"🖼 fallback extracted ref: {ref}")

                # 3) 最終URLを作成（該当ブロックをこれに差し替え）
                if ref:
                    if PUBLIC_BASE_URL:
                        photo_url = f"{PUBLIC_BASE_URL}/photo/{ref}.jpg?v={int(time.time())}"
                    else:
                        photo_url = str(request.url_for("photo_proxy", ref=f"{ref}.jpg"))
                        if photo_url.startswith("http://"):
                            photo_url = "https://" + photo_url[len("http://"):]
                        # 既に ? がある場合は &、無ければ ?
                        photo_url += f"&v={int(time.time())}" if "?" in photo_url else f"?v={int(time.time())}"
                else:
                    photo_url = ""

                logger.debug(f"🧩 photo_url for Flex: {photo_url}")

                bubble = build_ramen_flex(data, photo_url=photo_url, locale=locale)
                bubbles.append(bubble)

            if not bubbles:
                # 空返し（何もヒットしない場合も LINE には 200 を返す）
                return "OK"

            flex_carousel = {"type": "carousel", "contents": bubbles}
            message = FlexSendMessage(alt_text="餐廳資訊", contents=flex_carousel)
            line_bot_api.reply_message(event.reply_token, message)

    return "OK"
