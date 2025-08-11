import os
import re
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.models import FlexSendMessage
from linebot.exceptions import InvalidSignatureError
from ramen_qa import answer_ramen
# ← 追加（最上部）
from geo_utils import extract_location_from_text

app = FastAPI()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_TOKEN  = os.getenv("LINE_CHANNEL_TOKEN")
GOOGLE_API_KEY      = os.getenv("GOOGLE_API_KEY")
if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_TOKEN:
    raise RuntimeError("LINE_CHANNEL_SECRET と LINE_CHANNEL_TOKEN を設定してください")

line_bot_api = LineBotApi(LINE_CHANNEL_TOKEN)
parser = WebhookParser(LINE_CHANNEL_SECRET)


def parse_response_to_dict(text: str) -> dict:
    data = {}
    for line in text.splitlines():
        line = line.strip()
        if "：" in line:
            key, val = line.split("：", 1)
        elif ":" in line:
            key, val = line.split(":", 1)
        else:
            continue
        data[key.strip()] = val.strip()
    return data


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
#             "type": "text", "text": name, "weight": "bold", "size": "xl"
#         })

#     for key, prefix in [("地址", ""), ("捷運站", "捷運站："), ("價格", "價格："),
#                         ("推薦", "推薦："), ("特色", "特色："), ("營業時間", "營業時間：")]:
#         val = data.get(key)
#         if val:
#             if key == "營業時間":
#                 times = re.findall(r'\d{1,2}:\d{2}\s*–\s*\d{1,2}:\d{2}', val)
#                 val = "; ".join(times) if times else val
#             text = f"{prefix}{val}" if prefix else val
#             body_contents.append({
#                 "type": "text", "text": text, "size": "sm",
#                 "color": "#666666", "margin": "xs"
#             })

#     footer_buttons = []
#     link = data.get("Link", "")
#     if link and link.lower().startswith("http"):
#         footer_buttons.append({
#             "type": "button", "style": "link", "height": "sm",
#             "action": {"type": "uri", "label": "查看地圖", "uri": link}
#         })

#     flex = {
#         "type": "bubble",
#         "body": {"type": "box", "layout": "vertical", "contents": body_contents},
#     }

#     if footer_buttons:
#         flex["footer"] = {
#             "type": "box",
#             "layout": "vertical",
#             "spacing": "sm",
#             "contents": footer_buttons,
#             "flex": 0
#         }

#     return flex

def build_ramen_flex(data: dict, photo_url: str = "") -> dict:
    body_contents = []

    # 画像（任意）
    if photo_url:
        body_contents.append({
            "type": "image",
            "url": photo_url,
            "size": "full",
            "aspectMode": "cover",
            "aspectRatio": "20:13",
            "gravity": "top"
        })

    # 店名
    name = data.get("店名")
    if name:
        body_contents.append({
            "type": "text",
            "text": name,
            "weight": "bold",
            "size": "xl",
            "wrap": True
        })

    # 評価（店名直下）
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

    # その他
    for key, prefix in [
        ("地址", ""),
        ("捷運站", "捷運站："),
        # ("價格", "價格："),  # ← 価格を出さないなら外す
        ("推薦", "推薦："),
        ("特色", "特色："),
        ("營業時間", "營業時間："),
    ]:
        val = data.get(key)
        if not val:
            continue

        # 営業時間の時間帯だけ抽出（– or - 両対応）
        if key == "營業時間":
            times = re.findall(r'\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}', val)
            val = "; ".join(times) if times else val

        text_block = {
            "type": "text",
            "text": f"{prefix}{val}" if prefix else val,
            "size": "sm",
            "color": "#666666",
            "margin": "xs",
            "wrap": True
        }
        # 特色は長くなりがちなので3行に
        if key == "特色":
            text_block["maxLines"] = 3
        body_contents.append(text_block)

    # 地図リンク
    footer_buttons = []
    link = data.get("Link", "")
    if link and link.lower().startswith("http"):
        footer_buttons.append({
            "type": "button",
            "style": "link",
            "height": "sm",
            "action": {"type": "uri", "label": "查看地圖", "uri": link}
        })

    flex = {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "contents": body_contents},
    }
    if footer_buttons:
        flex["footer"] = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": footer_buttons,
            "flex": 0
        }
    return flex

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

#     # 店名
#     name = data.get("店名")
#     if name:
#         body_contents.append({
#             "type": "text", "text": name, "weight": "bold", "size": "xl"
#         })

#     # 評価を店名直下に
#     rating_val = data.get("評價")
#     if rating_val:
#         body_contents.append({
#             "type": "text", "text": f"評價：{rating_val}",
#             "size": "sm", "color": "#ff9900", "margin": "xs"
#         })

#     # その他の情報
#     for key, prefix in [
#         ("地址", ""),
#         ("捷運站", "捷運站："),
#         ("價格", "價格："),
#         ("推薦", "推薦："),
#         ("特色", "特色："),
#         ("營業時間", "營業時間：")
#     ]:
#         val = data.get(key)
#         if val:
#             if key == "營業時間":
#                 times = re.findall(r'\d{1,2}:\d{2}\s*–\s*\d{1,2}:\d{2}', val)
#                 val = "; ".join(times) if times else val
#             text = f"{prefix}{val}" if prefix else val
#             body_contents.append({
#                 "type": "text", "text": text, "size": "sm",
#                 "color": "#666666", "margin": "xs"
#             })

#     # 地図リンク
#     footer_buttons = []
#     link = data.get("Link", "")
#     if link and link.lower().startswith("http"):
#         footer_buttons.append({
#             "type": "button", "style": "link", "height": "sm",
#             "action": {"type": "uri", "label": "查看地圖", "uri": link}
#         })

#     flex = {
#         "type": "bubble",
#         "body": {"type": "box", "layout": "vertical", "contents": body_contents},
#     }
#     if footer_buttons:
#         flex["footer"] = {
#             "type": "box",
#             "layout": "vertical",
#             "spacing": "sm",
#             "contents": footer_buttons,
#             "flex": 0
#         }

#     return flex


from linebot.models import CarouselContainer

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

            # ✨ 地名から座標抽出して metadata_filter に変換
            lat, lng = extract_location_from_text(user_text, GOOGLE_API_KEY)
            metadata_filter = None
            if lat is not None and lng is not None:
                metadata_filter = {"location": {"lat": lat, "lng": lng}}

            # ⛳ 地名を反映した状態で検索
            raw_replies = answer_ramen(user_text, metadata_filters=metadata_filter)

            bubbles = []
            for result in raw_replies[:10]:
                data = parse_response_to_dict(result["text"])
                photo_url = result.get("photo_url", "")
                bubble = build_ramen_flex(data, photo_url=photo_url)
                bubbles.append(bubble)

            if not bubbles:
                return "OK"

            flex_carousel = {
                "type": "carousel",
                "contents": bubbles
            }

            message = FlexSendMessage(
                alt_text="拉麵店資訊（複数）",
                contents=flex_carousel
            )
            line_bot_api.reply_message(event.reply_token, message)

    return "OK"
