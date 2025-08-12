# google_review.py

import os
import json
import googlemaps
import re

# -------------------------------
# 設定
# -------------------------------
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    raise RuntimeError("Please set GOOGLE_PLACES_API_KEY environment variable")

OUTPUT_FILE = "ramen_google_reviews.json"

# -------------------------------
# 台北市内の seed 座標リスト
# -------------------------------
SEED_LOCATIONS = [
    ("台北車站", (25.0478, 121.5319)),
    ("中山區北部", (25.0802, 121.5268)),
    ("中山區南部", (25.0520, 121.5325)),
    ("大安區北部", (25.0386, 121.5431)),
    ("大安區南部", (25.0203, 121.5437)),
    ("信義區北部", (25.0405, 121.5600)),
    ("信義區南部", (25.0282, 121.5773)),
    ("萬華區", (25.0356, 121.5007)),
    ("中正區", (25.0335, 121.5192)),
    ("松山區", (25.0593, 121.5573)),
    ("士林區", (25.0952, 121.5250)),
    ("內湖區北部", (25.0960, 121.5900)),
    ("內湖區南部", (25.0800, 121.5750)),
    ("南港區", (25.0495, 121.6172)),
    ("北投區西部", (25.1191, 121.4980)),
    ("北投區東部", (25.1320, 121.5400)),
    ("文山區西部", (24.9886, 121.5450)),
    ("文山區東部", (24.9820, 121.5700)),
    ("大同區", (25.0617, 121.5151)),
    ("內湖科技園區", (25.0832, 121.5645)),
    ("圓山站", (25.0727, 121.5196)),
    ("古亭站", (25.0254, 121.5262)),
    ("西門町", (25.0423, 121.5079)),
    ("公館", (25.0169, 121.5332)),
    ("天母", (25.1167, 121.5266)),
]

# -------------------------------
# 初期化
# -------------------------------
gmaps = googlemaps.Client(key=API_KEY)

if os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        entries = json.load(f)
else:
    entries = []

existing_urls = {e["url"] for e in entries}
existing_place_ids = set()  # place_id でも重複排除
total_new_count = 0

# -------------------------------
# メイン処理
# -------------------------------
for area_name, center in SEED_LOCATIONS:
    print(f"\n📍 Searching: {area_name}")
    places_result = gmaps.places_nearby(
        location=center,
        radius=1000,
        type="restaurant",
        keyword="拉麵",
        language="zh-TW"
    ).get("results", [])

    new_count = 0

    for p in places_result:
        place_id = p["place_id"]
        if place_id in existing_place_ids:
            continue

        details = gmaps.place(
            place_id=place_id,
            fields=[
                "name", "formatted_address", "geometry", "vicinity",
                "website", "rating", "user_ratings_total", "reviews",
                "opening_hours", "price_level", "photo"
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

        # 価格帯変換
        price_level = details.get("price_level", 0)
        PRICE_LEVEL_MAP = {
            0: "NT$～200",
            1: "NT$～200",
            2: "NT$200～400",
            3: "NT$400～800",
            4: "NT$800以上",
        }
        price_range = PRICE_LEVEL_MAP.get(price_level, "價格資訊缺乏")

        # 写真URL取得
        photos = details.get("photos", [])
        photo_reference = photos[0]["photo_reference"] if photos else None
        photo_url = (
            f"https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth=800&photo_reference={photo_reference}&key={API_KEY}"
        ) if photo_reference else None

        from urllib.parse import quote_plus

        # 店名と住所から maps_url を構築
        search_query = f"{name} {details.get('formatted_address', '')}"
        maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(search_query)}"

        metadata = {
            "source": "google_places",
            "address": details.get("formatted_address", ""),
            "location": {"lat": lat, "lng": lng},
            "rating": details.get("rating"),
            "reviews_count": details.get("user_ratings_total"),
            "mrt_stations": mrt_stations,
            "bus_stations": bus_stations,
            "maps_url": maps_url,  # ←ここ変更
            "opening_hours": {
                "weekday_text": details.get("opening_hours", {}).get("weekday_text")
            },
            "price_range": price_range,
            "photo_url": photo_url
        }

        # 登録
        entry = {
            "title": name,
            "text": text,
            "url": url,
            "metadata": metadata
        }
        entries.append(entry)
        existing_urls.add(url)
        existing_place_ids.add(place_id)
        new_count += 1

        print(f"✅ {name} added.")

    print(f"✅ {area_name}: {new_count} new places.")
    total_new_count += new_count

# -------------------------------
# 保存
# -------------------------------
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)

print(f"\n✅ All done. Total new places: {total_new_count}. Total entries: {len(entries)}")
