# google_review_2.py

import os
import json
import googlemaps
#from serpapi import GoogleSearch

# -----------------------------------------------------------------------------
# 設定
# -----------------------------------------------------------------------------
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
# SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not API_KEY:
    raise RuntimeError("Please set GOOGLE_PLACES_API_KEY environment variable")
# if not SERPAPI_KEY:
#     raise RuntimeError("Please set SERPAPI_KEY environment variable for SerpAPI")

OUTPUT_FILE = "ramen_google_reviews.json"
CENTER_LOCATION = (25.0478, 121.5319)  # 台北駅

# -----------------------------------------------------------------------------
# クライアント初期化
# -----------------------------------------------------------------------------
gmaps = googlemaps.Client(key=API_KEY)

# -----------------------------------------------------------------------------
# 既存 JSON 読み込み（重複排除用）
# -----------------------------------------------------------------------------
if os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        entries = json.load(f)
else:
    entries = []
existing_urls = {e["url"] for e in entries}

# -----------------------------------------------------------------------------
# 1) ラーメン店検索
# -----------------------------------------------------------------------------
places_result = gmaps.places_nearby(
    location=CENTER_LOCATION,
    radius=5000,
    type="restaurant",
    keyword="拉麵",
    language="zh-TW"
).get("results", [])
# デバッグ用: 最初の1件だけ処理
#places_result = places_result[:1]  # テスト時は1件に絞る
new_count = 0

for p in places_result:
    place_id = p["place_id"]
    # 2) 詳細取得
    details = gmaps.place(
        place_id=place_id,
        fields=[
            "name", "formatted_address", "geometry", "vicinity",
            "website", "rating", "user_ratings_total", "reviews", "opening_hours","price_level", "photo"
        ],
        language="zh-TW"
    ).get("result", {})

    name = details.get("name")
    url = details.get("website") or details.get("vicinity")
    if not url or url in existing_urls:
        continue

    # 緯度経度
    loc = details.get("geometry", {}).get("location", {})
    lat, lng = loc.get("lat"), loc.get("lng")

    # 駅・バス停取得
    mrt_results = gmaps.places_nearby(
        location=(lat, lng), radius=800,
        type="subway_station", language="zh-TW"
    ).get("results", [])
    mrt_stations = [s["name"] for s in mrt_results[:3]]

    bus_results = gmaps.places_nearby(
        location=(lat, lng), radius=800,
        type="bus_station", language="zh-TW"
    ).get("results", [])
    bus_stations = [b["name"] for b in bus_results[:3]]

    # レビュー本文
    reviews = details.get("reviews", [])
    text = "\n".join(r.get("text", "") for r in reviews)
    maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    price_level = details.get("price_level", 0)
    # 取得した price_level (0～4) を NT$ のレンジ文字列にマッピング
    PRICE_LEVEL_MAP = {
        0: "NT$～200",          # プロモーションなど
        1: "NT$～200",     # 軽食、屋台レベル
        2: "NT$200～400",   # 一般的なラーメン店
        3: "NT$400～800",   # 中級レストラン
        4: "NT$800以上",     # 高級店
    }

    # マップを参照して文字列に変換（マップにない値は「不明」としておく）
    price_range = PRICE_LEVEL_MAP.get(price_level, "価格情報なし")

    import re

    photos = details.get("photos", [])
    print(f"[DEBUG] name={name}")
    print(f"[DEBUG] photos={photos}")
    photo_reference = photos[0]["photo_reference"] if photos else None
    photo_url = (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photo_reference={photo_reference}&key={API_KEY}"
    ) if photo_reference else None


    print(f"店名: {name}")
    print(f"Photo URL: {photo_url}")


    # メタデータ作成
    metadata = {
        "source": "google_places",
        "address" : details.get("formatted_address", ""),
        "location": {"lat": lat, "lng": lng},
        "rating": details.get("rating"),
        "reviews_count": details.get("user_ratings_total"),
        "mrt_stations": mrt_stations,
        "bus_stations": bus_stations,
        "maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
        "opening_hours": {"weekday_text": details.get("opening_hours", {}).get("weekday_text")},
        "price_range":price_range,
        "photo_url": photo_url

        #"price_range": price_range,
        #"top_menu_photo": top_photo
    }

    entry = {"title": name, "text": text, "url": url, "metadata": metadata}
    entries.append(entry)
    existing_urls.add(url)
    new_count += 1
    #print(f"Added: {name} | Price: {price_range} | MenuImage: {top_photo}")

# 保存
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)
print(f"✅ Completed. {new_count} new places added. Total: {len(entries)} entries.")
