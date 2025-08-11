# parse_articles_to_json.py

import json
import requests
import time
import random
from bs4 import BeautifulSoup

# まとめ記事判定キーワード
LISTICLE_KEYWORDS = ["ランキング", "選", "top", "トップ","Top","TOP"]

# User-Agent ヘッダー
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    )
}

def fetch_title(url: str, retries: int = 3) -> str:
    """<title> または <h1> からタイトル取得。429ならリトライ。"""
    for attempt in range(1, retries + 1):
        try:
            time.sleep(random.uniform(1.0, 2.0))  # リクエスト前に待機
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            if title_tag := soup.select_one("title"):
                return title_tag.text.strip()
            if h1 := soup.select_one("h1"):
                return h1.text.strip()
            return url
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429 and attempt < retries:
                wait = 5 * attempt  # 5秒 × 試行回数
                print(f"⚠️ 429 detected for {url}, retrying in {wait}s (attempt {attempt})")
                time.sleep(wait)
                continue
            print(f"⚠️ Failed to fetch title for {url}: {e}")
            return url
        except Exception as e:
            print(f"⚠️ Error fetching title for {url}: {e}")
            return url

def parse_article(url: str) -> list[dict]:
    """通常記事を1エントリとしてパース。"""
    try:
        time.sleep(random.uniform(1.0, 2.0))
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️ Skipping article {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    title_el = soup.select_one("h1") or soup.select_one("title")
    title = title_el.get_text(strip=True) if title_el else url

    paras = soup.select("div.content p") or soup.select("article p") or soup.find_all("p")
    body = "\n".join(p.get_text(strip=True) for p in paras)
    return [{"title": title, "text": body, "url": url}]

def parse_listicle(url: str) -> list[dict]:
    """まとめ記事を見出しごとに分割してパース。"""
    try:
        time.sleep(random.uniform(1.0, 2.0))
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️ Skipping listicle {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    headings = soup.select("div.content-area h2")
    if not headings:
        return parse_article(url)

    entries = []
    for h2 in headings:
        shop = h2.get_text(strip=True)
        desc = []
        for sib in h2.next_siblings:
            if getattr(sib, "name", None) == "h2":
                break
            if getattr(sib, "get_text", None):
                txt = sib.get_text(strip=True)
                if txt: desc.append(txt)
        entries.append({"title": shop, "text": "\n".join(desc), "url": url})
    return entries

def main():
    with open("article_urls.json", "r", encoding="utf-8") as f:
        urls = json.load(f)

    try:
        with open("processed_urls.json", "r", encoding="utf-8") as f:
            processed = set(json.load(f))
    except FileNotFoundError:
        processed = set()

    all_entries = []
    new_processed = []

    for url in urls:
        if url in processed:
            continue

        title = fetch_title(url)
        if any(k in title for k in LISTICLE_KEYWORDS):
            print("Listicle:", title)
            parsed = parse_listicle(url)
        else:
            print("Article :", title)
            parsed = parse_article(url)

        all_entries.extend(parsed)
        new_processed.append(url)

    with open("parsed_entries.json", "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    print(f"✅ Parsed {len(all_entries)} entries → parsed_entries.json")

    processed.update(new_processed)
    with open("processed_urls.json", "w", encoding="utf-8") as f:
        json.dump(list(processed), f, ensure_ascii=False, indent=2)
    print(f"✅ Updated processed URLs ({len(processed)}) → processed_urls.json")

if __name__ == "__main__":
    main()



# # parse_articles_to_json.py

# import json
# import requests
# from bs4 import BeautifulSoup
# import time
# import random

# # まとめ記事判定キーワード
# LISTICLE_KEYWORDS = ["ランキング", "選", "top", "トップ","Top","TOP"]

# def fetch_title(url: str) -> str:
#     """<title> または <h1> タグからタイトルを取得"""
#     resp = requests.get(url)
#     resp.raise_for_status()
#     soup = BeautifulSoup(resp.text, "html.parser")
#     if title_tag := soup.select_one("title"):
#         return title_tag.text.strip()
#     if h1 := soup.select_one("h1"):
#         return h1.text.strip()
#     return url  # 最終手段は URL をタイトル代わりに

# def parse_article(url: str) -> list[dict]:
#     """
#     通常記事を1エントリとしてパース。
#     <h1> がなければ fetch_title() を使い、
#     本文は <div.content p> → <article p> → 全 p タグ の順で取得。
#     """
#     resp = requests.get(url); resp.raise_for_status()
#     soup = BeautifulSoup(resp.text, "html.parser")

#     # タイトル
#     title = (soup.select_one("h1") or soup.select_one("title"))
#     title = title.get_text(strip=True) if title else url

#     # 本文パラグラフの取得候補
#     paras = soup.select("div.content p")
#     if not paras:
#         paras = soup.select("article p")
#     if not paras:
#         paras = soup.find_all("p")

#     body = "\n".join(p.get_text(strip=True) for p in paras)

#     return [{
#         "title": title,
#         "text": body,
#         "url": url
#     }]

# def parse_listicle(url: str) -> list[dict]:
#     """
#     見出し(h2)ごとに分割するまとめ記事用パーサー。
#     見出しが取れなければ単一記事扱いにフォールバックします。
#     """
#     resp = requests.get(url); resp.raise_for_status()
#     soup = BeautifulSoup(resp.text, "html.parser")

#     headings = soup.select("div.content-area h2")
#     if not headings:
#         # 見出しがない場合は普通の記事として扱う
#         return parse_article(url)

#     entries = []
#     for h2 in headings:
#         shop = h2.get_text(strip=True)
#         desc = []
#         for sib in h2.next_siblings:
#             if getattr(sib, "name", None) == "h2":
#                 break
#             if getattr(sib, "get_text", None):
#                 txt = sib.get_text(strip=True)
#                 if txt:
#                     desc.append(txt)
#         entries.append({
#             "title": shop,
#             "text": "\n".join(desc),
#             "url": url
#         })
#     return entries

# def main():
#     # 1) URLリスト読み込み
#     with open("article_urls.json", "r", encoding="utf-8") as f:
#         urls = json.load(f)

#     # 2) 既処理 URL 読み込み
#     try:
#         with open("processed_urls.json", "r", encoding="utf-8") as f:
#             processed = set(json.load(f))
#     except FileNotFoundError:
#         processed = set()

#     all_entries = []
#     new_processed = []

#     for url in urls:
#         if url in processed:
#             continue  # 既処理はスキップ
#         time.sleep(random.uniform(3, 4))

#         title = fetch_title(url)
#         if any(k in title for k in LISTICLE_KEYWORDS):
#             print("Listicle:", title)
#             parsed = parse_listicle(url)
#         else:
#             print("Article :", title)
#             parsed = parse_article(url)
#         all_entries.extend(parsed)
#         new_processed.append(url)

#     # 3) parsed_entries.json に出力
#     with open("parsed_entries.json", "w", encoding="utf-8") as f:
#         json.dump(all_entries, f, ensure_ascii=False, indent=2)
#     print(f"✅ Parsed {len(all_entries)} entries → parsed_entries.json")

#     # 4) processed_urls.json を更新
#     processed.update(new_processed)
#     with open("processed_urls.json", "w", encoding="utf-8") as f:
#         json.dump(list(processed), f, ensure_ascii=False, indent=2)
#     print(f"✅ Updated processed URLs ({len(processed)}) → processed_urls.json")

# if __name__ == "__main__":
#     main()

# # parse_articles_to_json.py

# import json
# import requests
# from bs4 import BeautifulSoup

# # まとめ記事判定キーワード
# LISTICLE_KEYWORDS = ["ランキング", "選"]

# def fetch_title(url: str) -> str:
#     resp = requests.get(url)
#     resp.raise_for_status()
#     soup = BeautifulSoup(resp.text, "html.parser")
#     if title_tag := soup.select_one("title"):
#         return title_tag.text.strip()
#     if h1 := soup.select_one("h1"):
#         return h1.text.strip()
#     return ""

# def parse_article(url: str) -> list[dict]:
#     resp = requests.get(url); resp.raise_for_status()
#     soup = BeautifulSoup(resp.text, "html.parser")
#     title = soup.select_one("h1").get_text(strip=True)
#     body = "\n".join(p.get_text(strip=True) for p in soup.select("div.content p"))
#     return [{"title": title, "text": body, "url": url}]

# def parse_listicle(url: str) -> list[dict]:
#     resp = requests.get(url); resp.raise_for_status()
#     soup = BeautifulSoup(resp.text, "html.parser")
#     entries = []
#     # サイトに合わせてタグ・セレクタを調整してください
#     headings = soup.select("div.content-area h2")
#     for h2 in headings:
#         shop = h2.get_text(strip=True)
#         desc = []
#         for sib in h2.next_siblings:
#             if getattr(sib, "name", None) == "h2":
#                 break
#             if getattr(sib, "get_text", None):
#                 txt = sib.get_text(strip=True)
#                 if txt:
#                     desc.append(txt)
#         entries.append({
#             "title": shop,
#             "text": "\n".join(desc),
#             "url": url
#         })
#     return entries

# def main():
#     # 1) URLリスト読み込み
#     with open("article_urls.json", "r", encoding="utf-8") as f:
#         urls = json.load(f)

#     # 2) 既処理URLの読み込み or 空リスト作成
#     try:
#         with open("processed_urls.json", "r", encoding="utf-8") as f:
#             processed = set(json.load(f))
#     except FileNotFoundError:
#         processed = set()

#     all_entries = []
#     new_processed = []

#     for url in urls:
#         if url in processed:
#             continue  # 重複はスキップ
#         title = fetch_title(url)
#         if any(k in title for k in LISTICLE_KEYWORDS):
#             print("Listicle:", title)
#             parsed = parse_listicle(url)
#         else:
#             print("Single :", title)
#             parsed = parse_article(url)
#         all_entries.extend(parsed)
#         new_processed.append(url)

#     # 3) パース結果をJSONで出力
#     with open("parsed_entries.json", "w", encoding="utf-8") as f:
#         json.dump(all_entries, f, ensure_ascii=False, indent=2)
#     print(f"✅ Parsed {len(all_entries)} entries → parsed_entries.json")

#     # 4) processed_urls.json を更新
#     processed.update(new_processed)
#     with open("processed_urls.json", "w", encoding="utf-8") as f:
#         json.dump(list(processed), f, ensure_ascii=False, indent=2)
#     print(f"✅ Updated processed URLs ({len(processed)} total) → processed_urls.json")

# if __name__ == "__main__":
#     main()
