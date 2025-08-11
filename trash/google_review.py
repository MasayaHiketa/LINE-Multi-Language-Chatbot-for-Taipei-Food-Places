# google_review.py

import os
import json
import googlemaps

# -----------------------------------------------------------------------------
# 設定
# -----------------------------------------------------------------------------
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    raise RuntimeError("Please set GOOGLE_PLACES_API_KEY environment variable")

OUTPUT_FILE = "ramen_google_reviews.json"

# 検索中心（台北駅周辺）
CENTER_LOCATION = (25.0478, 121.5319)

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
    keyword="拉麵",       # 繁体字「ラーメン」
    language="zh-TW"
).get("results", [])

new_count = 0

for p in places_result:
    place_id = p["place_id"]
    # 2) 詳細取得
    details = gmaps.place(
        place_id=place_id,
        fields=[
            "name",
            "formatted_address",
            "geometry",
            "vicinity",
            "website",
            "rating",
            "user_ratings_total",
            "reviews",
            "opening_hours"
        ],
        language="zh-TW"
    ).get("result", {})

    maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    name = details.get("name")
    # URL として優先的に website、なければ vicinity
    url = details.get("website") or details.get("vicinity")
    if not url or url in existing_urls:
        continue  # 重複または URL なしはスキップ

    # 緯度経度
    loc = details.get("geometry", {}).get("location", {})
    lat, lng = loc.get("lat"), loc.get("lng")

    # 🚇 MRT（捷運）駅を上位3件取得
    mrt_results = gmaps.places_nearby(
        location=(lat, lng),
        radius=800,
        type="subway_station",   # 「捷運」には 'subway_station'
        language="zh-TW"
    ).get("results", [])
    mrt_stations = [s["name"] for s in mrt_results[:3]]

    # 🚌 バス停を上位3件取得
    bus_results = gmaps.places_nearby(
        location=(lat, lng),
        radius=800,
        type="bus_station",      # 「バス停」には 'bus_station'
        language="zh-TW"
    ).get("results", [])
    bus_stations = [b["name"] for b in bus_results[:3]]
    # レビュー本文をまとめる
    reviews = details.get("reviews", [])
    text = "\n".join(r.get("text", "") for r in reviews)
    # --- そのほかのメタデータ同様に組み立て ---
    metadata = {
        "source": "google_places",
        "address": details.get("formatted_address"),
        "location": {"lat": lat, "lng": lng},
        "rating": details.get("rating"),
        "reviews_count": details.get("user_ratings_total"),
        "mrt_stations": mrt_stations,    # 追加
        "bus_stations": bus_stations,     # 追加
        "maps_url":     maps_url,
        "opening_hours": {
            #"open_now": details.get("opening_hours", {}).get("open_now"),
            #"periods":  details.get("opening_hours", {}).get("periods"),
            "weekday_text": details.get("opening_hours", {}).get("weekday_text"),
        }
    }

    entry = {
        "title": name,
        "text": text,
        "url": url,
        "metadata": metadata
    }
    entries.append(entry)
    existing_urls.add(url)
    new_count += 1
    print(f"Added: {name} ({url}) near station: {mrt_stations}")

# -----------------------------------------------------------------------------
# 追記した結果を JSON に保存
# -----------------------------------------------------------------------------
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)

print(f"✅ Completed. {new_count} new places added. Total entries: {len(entries)}")
