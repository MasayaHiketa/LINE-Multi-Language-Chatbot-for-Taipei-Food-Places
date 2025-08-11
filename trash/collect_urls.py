# collect_urls.py

import json
from serpapi import GoogleSearch

# 1) SerpAPI キー
API_KEY = "e7de69007124fc526668e3db4331bc3165a8b94485dc3e3e249980e03789e940"

# 2) 検索パラメータ
params = {
    "engine": "google",
    "q": "台北 ラーメン ブログ",
    "hl": "ja",
    "gl": "jp",
    "api_key": API_KEY,
    "num": 100  # 取得件数
}

# 3) 実行
search = GoogleSearch(params)
results = search.get_dict()

# 4) 上位結果の URL を抽出
urls = [r["link"] for r in results.get("organic_results", [])]

# 5) JSON に保存
with open("article_urls.json", "w", encoding="utf-8") as f:
    json.dump(urls, f, ensure_ascii=False, indent=2)

print("✅ Saved URLs to article_urls.json")
