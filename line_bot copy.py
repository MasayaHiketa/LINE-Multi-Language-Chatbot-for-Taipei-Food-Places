# line_bot.py

import os
import re
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.models import FlexSendMessage
from linebot.exceptions import InvalidSignatureError
from ramen_qa import answer_ramen  # QA 用の関数をインポート

app = FastAPI()

# 環境変数からLINEチャネル情報を取得
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_TOKEN  = os.getenv("LINE_CHANNEL_TOKEN")
if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_TOKEN:
    raise RuntimeError("LINE_CHANNEL_SECRET と LINE_CHANNEL_TOKEN を設定してください")

line_bot_api = LineBotApi(LINE_CHANNEL_TOKEN)
parser        = WebhookParser(LINE_CHANNEL_SECRET)


def parse_response_to_dict(text: str) -> dict:
    """
    answer_ramen の出力（鍵：値 の文字列）を
    Python の dict に変換するヘルパー
    """
    data = {}
    for line in text.splitlines():
        # 全角 or 半角コロンの両方に対応
        line = line.strip()
        if "：" in line:
            key, val = line.split("：", 1)
        elif ":" in line:
            key, val = line.split(":", 1)
        else:
            continue
        data[key.strip()] = val.strip()
    return data

# def build_ramen_flex(data: dict) -> dict:
#     # ボディ部の contents を空リストで初期化
#     body_contents = []

#     # 店名（必須とする）
#     name = data.get("店名")
#     if name:
#         body_contents.append({
#             "type": "text", "text": name, "weight": "bold", "size": "xl"
#         })

#     # それ以外のフィールドは値があれば追加
#     for key, prefix in [("地址", ""), ("捷運站", "捷運站："), ("價格", "價格："),
#                         ("推薦", "推薦："), ("特色", "特色："),("營業時間", "營業時間：")]:
#         val = data.get(key)
#         if val:
#             text = f"{prefix}{val}" if prefix else val
#             body_contents.append({
#                 "type": "text", "text": text, "size": "sm",
#                 "color": "#666666", "margin": "xs"
#             })

#     # フッター部のボタンを動的に組み立て
#     footer_buttons = []
#     link = data.get("Link", "")
#     if link and link.lower().startswith("http"):
#         footer_buttons.append({
#             "type": "button", "style": "link", "height": "sm",
#             "action": {"type": "uri", "label": "查看地圖", "uri": link}
#         })

#     # Flex bubble のひな型
#     flex = {
#       "type": "bubble",
#       "body": {"type": "box", "layout": "vertical", "contents": body_contents},
#     }

#     # ボタンがあれば footer に追加
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
            "type": "text", "text": name, "weight": "bold", "size": "xl"
        })

    for key, prefix in [("地址", ""), ("捷運站", "捷運站："), ("價格", "價格："),
                        ("推薦", "推薦："), ("特色", "特色："), ("營業時間", "營業時間：")]:
        val = data.get(key)
        if val:
            if key == "營業時間":
                # 時間だけ抽出（例："10:00 – 22:00"）
                times = re.findall(r'\d{1,2}:\d{2}\s*–\s*\d{1,2}:\d{2}', val)
                val = "; ".join(times) if times else val

            text = f"{prefix}{val}" if prefix else val
            body_contents.append({
                "type": "text", "text": text, "size": "sm",
                "color": "#666666", "margin": "xs"
            })

    footer_buttons = []
    link = data.get("Link", "")
    if link and link.lower().startswith("http"):
        footer_buttons.append({
            "type": "button", "style": "link", "height": "sm",
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

# def build_ramen_flex(data: dict) -> dict:
#     # ボディ部の contents を空リストで初期化
#     body_contents = []

#     # 店名（必須とする）
#     name = data.get("店名")
#     if name:
#         body_contents.append({
#             "type": "text", "text": name, "weight": "bold", "size": "xl"
#         })

#     # それ以外のフィールドは値があれば追加
#     for key, prefix in [("地址", ""), ("捷運站", "捷運站："), ("價格", "價格："),
#                         ("推薦", "推薦："), ("特色", "特色："),("營業時間", "營業時間：")]:
#         val = data.get(key)
#         if val:
#             text = f"{prefix}{val}" if prefix else val
#             body_contents.append({
#                 "type": "text", "text": text, "size": "sm",
#                 "color": "#666666", "margin": "xs"
#             })

#     # フッター部のボタンを動的に組み立て
#     footer_buttons = []
#     link = data.get("Link", "")
#     if link and link.lower().startswith("http"):
#         footer_buttons.append({
#             "type": "button", "style": "link", "height": "sm",
#             "action": {"type": "uri", "label": "查看地圖", "uri": link}
#         })

#     # Flex bubble のひな型
#     flex = {
#         "type": "bubble",
#         "body": {"type": "box", "layout": "vertical", "contents": body_contents},
#     }

#     # 画像があれば hero に追加
#     photo_url = data.get("圖片", "")
#     if photo_url and photo_url.lower().startswith("http"):
#         flex["hero"] = {
#             "type": "image",
#             "url": photo_url,
#             "size": "full",
#             "aspectRatio": "20:13",
#             "aspectMode": "cover"
#         }

#     # フッター部があれば追加
#     if footer_buttons:
#         flex["footer"] = {
#             "type": "box",
#             "layout": "vertical",
#             "spacing": "sm",
#             "contents": footer_buttons,
#             "flex": 0
#         }

#     return flex

from linebot.models import FlexSendMessage, CarouselContainer

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
            raw_replies = answer_ramen(user_text)  # ← 返り値は list[dict]
            bubbles = []
            for result in raw_replies[:10]:
                data = parse_response_to_dict(result["text"])
                photo_url = result.get("photo_url", "")
                bubble = build_ramen_flex(data, photo_url=photo_url)  # ← 新引数
                bubbles.append(bubble)

            # # ① QA ロジックで複数店舗分の文字列を取得（ここは仮）
            # raw_replies = answer_ramen(user_text)  # たとえば "\n---\n" で区切る設計に
            # raw_chunks = raw_replies.split("\n---\n")

            # bubbles = []
            # for raw in raw_chunks[:10]:  # LINE Flex の最大バブル数は 10
            #     data = parse_response_to_dict(raw)
            #     print("DEBUG dict:\n", data)

            #     bubble = build_ramen_flex(data)
            #     bubbles.append(bubble)

            if not bubbles:
                return "OK"

            flex_carousel = {
                "type": "carousel",
                "contents": bubbles
            }

            message = FlexSendMessage(alt_text="拉麵店資訊（複数）", contents=flex_carousel)
            line_bot_api.reply_message(event.reply_token, message)

    return "OK"


