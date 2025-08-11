# geo_utils.py

import requests
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo")

def extract_location_from_text(text: str, api_key: str):
    try:
        # LLM で地名抽出
        prompt = f"""以下の質問文に含まれる「台湾の地名または住所のみ」を1つだけ抽出してください。
形式は「中山」「信義區」「西門町」「永康街」などで、町名・駅名・観光地でも構いません。
文章全体ではなく、場所の名前だけを出力してください。

質問文：
{text}

出力（地名のみ）：
"""
        place = llm.predict(prompt).strip()

        if not place:
            return None, None

        # ジオコード変換
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": f"台北 {place}", "key": api_key}
        )
        results = resp.json().get("results", [])
        if results:
            loc = results[0]["geometry"]["location"]
            return loc["lat"], loc["lng"]

    except Exception as e:
        print(f"[ERROR] 地名抽出/座標変換失敗: {e}")
        return None, None

    return None, None
