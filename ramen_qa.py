#ramen_qa.py

import os
import re
from typing import Optional, Dict, Any, List
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from langchain_community.vectorstores.faiss import FAISS
from langchain.prompts import PromptTemplate
from langdetect import detect
import googlemaps
from geopy.distance import geodesic

# ───────────────────────────────────────
# 環境変数と初期化
# ───────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not OPENAI_API_KEY or not GOOGLE_MAPS_API_KEY:
    raise RuntimeError("APIキーが設定されていません。")

_embedding = OpenAIEmbeddings()
_llm = ChatOpenAI(model="gpt-3.5-turbo")
_INDEX_PATH = "faiss_index"
_gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

try:
    _vectorstore = FAISS.load_local(_INDEX_PATH, _embedding, allow_dangerous_deserialization=True)
except Exception:
    _vectorstore = None

_qa_chain: Optional[RetrievalQA] = None

# ───────────────────────────────────────
# カスタムプロンプト
# ───────────────────────────────────────
QA_PROMPT = PromptTemplate(
    template="""\
您是台北的餐廳導覽 AI，請根據以下參考資料，對提問做出簡潔且具體的回答。
**請優先考慮「問題中提及的地點」與「捷運站」欄位最接近的餐廳，最多給出3家。**
可以包含任何類型的餐飲（中式、西式、日本料理、甜點、咖啡廳等）。

請僅以以下格式，每家店之間以 `---` 分隔，並不要加入其他說明文字或語句。

問題：
{question}

參考資料：
{context}

輸出格式（最多三家）：

店名：  
地址：   
評價：  
推薦：  
特色：
營業時間:
""",
    input_variables=["context", "question"]
)

# QA_PROMPT = PromptTemplate(
#     template="""\
# 您是台北的拉麵導覽 AI，請根據以下參考資料，對提問做出簡潔且具體的回答。
# **請優先考慮「問題中提及的地點」與「捷運站」欄位最接近的店家，最多給出3家。**

# 請僅以以下格式，每家店之間以 `---` 分隔，並不要加入其他說明文字或語句。

# 問題：
# {question}

# 參考資料：
# {context}

# 輸出格式（最多三家）：

# 店名：  
# 地址：   
# 評價：  
# 推薦：  
# 特色：
# 營業時間:
# """,
#     input_variables=["context", "question"]
# )

# ───────────────────────────────────────
# ヘルパー：地名→座標
# ───────────────────────────────────────
def extract_address(text: str) -> Optional[str]:
    match = re.search(r"(台北市|台灣台北市)?[^\s\d]{1,6}(區|路|站)[^\n，。 ]{1,10}", text)
    return match.group(0) if match else None

def geocode_location(address: str) -> Optional[tuple]:
    try:
        geocode = _gmaps.geocode(address)
        if geocode and len(geocode) > 0:
            loc = geocode[0]["geometry"]["location"]
            return (loc["lat"], loc["lng"])
    except:
        return None
    return None

# ───────────────────────────────────────
# QA チェーン初期化
# ───────────────────────────────────────
def _init_qa_chain(filters: Optional[Dict[str, Any]] = None):
    global _qa_chain
    if _qa_chain is None or filters is not None:
        if _vectorstore is None:
            raise RuntimeError(f"FAISS index not found at '{_INDEX_PATH}'。")
        retriever = _vectorstore.as_retriever(search_kwargs={"filter": filters or {}, "k": 5})
        _qa_chain = RetrievalQA.from_chain_type(
            llm=_llm,
            retriever=retriever,
            chain_type="stuff",
            chain_type_kwargs={"prompt": QA_PROMPT}
        )

# ───────────────────────────────────────
# QA 実行
# ───────────────────────────────────────
def answer_ramen(query: str, metadata_filters: Optional[Dict[str, Any]] = None) -> List[dict]:
    from langchain.docstore.document import Document

    src_lang = detect(query)
    zh_query = query if src_lang.startswith("zh") else _translate(query, 'zh')

    # 地名 → 座標取得（任意：実装済みなら使われます）
    address = extract_address(query)
    query_coord = geocode_location(address) if address else None

    # FAISS検索（10件）
    docs = _vectorstore.similarity_search(zh_query, k=10)

    # 距離補正：近い順に並び替え（query_coord が取れたときだけ）
    if query_coord:
        def dist(doc):
            loc = doc.metadata.get("location")
            if loc:
                return geodesic(query_coord, (loc["lat"], loc["lng"])).meters
            return float("inf")
        docs.sort(key=dist)

    # QA 実行
    _init_qa_chain(filters=metadata_filters)
    raw = _qa_chain.invoke({"query": zh_query}).get("result", "")
    blocks = [b.strip() for b in raw.strip().split('---') if b.strip()]

    results = []
    for block in blocks:
        processed = _post_process(block)

        # 店名抽出（なければスキップ）
        store_name = None
        for line in processed.splitlines():
            if line.startswith("店名："):
                store_name = line.replace("店名：", "").strip()
                break
        if not store_name:
            continue

        # メタ一致（maps_url / photo / rating / reviews）
        matched_url = "N/A"
        matched_photo = ""
        matched_rating = None
        matched_reviews = None
        for doc in docs:
            title = doc.metadata.get("title", "")
            if store_name in title:
                matched_url     = doc.metadata.get("maps_url", "N/A")
                matched_photo   = doc.metadata.get("photo_url", "")
                matched_rating  = doc.metadata.get("rating", None)
                matched_reviews = doc.metadata.get("reviews_count", None)
                break

        # 評価行を構築（★と☆で5段階／数値／件数）
        rating_line = None
        if matched_rating is not None:
            try:
                r = float(matched_rating)
                full_stars = max(0, min(5, int(round(r))))
                star_str = "★" * full_stars + "☆" * (5 - full_stars)
                if isinstance(matched_reviews, int):
                    rating_line = f"評價：{star_str} {r:.1f}（{matched_reviews:,}）"
                else:
                    rating_line = f"評價：{star_str} {r:.1f}"
            except Exception:
                rating_line = None  # 異常値なら無視

        # ここで必ず最新の lines を組み立て直す
        lines = processed.splitlines()

        # 既存の LLM 由来の「評價：」と「Link：」は一旦除去してから再構成
        lines = [l for l in lines if not l.startswith("評價：") and not l.startswith("Link：")]

        # 店名直下に 評價 行を差し込む（メタデータ優先）
        if rating_line:
            inserted = False
            for i, l in enumerate(lines):
                if l.startswith("店名："):
                    lines.insert(i + 1, rating_line)
                    inserted = True
                    break
            if not inserted:
                # 念のため（店名が見つからない想定外ケース）
                lines.insert(0, rating_line)

        # Link 行は最後に1本だけ
        lines.append(f"Link：{matched_url}")

        final_text = "\n".join(lines)

    # # final_text = ... を作った後の部分を差し替え
    # if not src_lang.startswith("zh"):
    #     translated_lines = []
    #     for ln in lines:
    #         # 全角/半角コロン対応で key / val に分割
    #         if "：" in ln:
    #             key, val = ln.split("：", 1)
    #             colon = "："
    #         elif ":" in ln:
    #             key, val = ln.split(":", 1)
    #             colon = ":"
    #         else:
    #             translated_lines.append(ln)
    #             continue

    #         key = key.strip()
    #         val = val.strip()

    #         # 店名とLinkの値は翻訳しない（店名は固有名詞、LinkはURL）
    #         if key in ("店名", "Link"):
    #             translated_val = val
    #         else:
    #             translated_val = _translate(val, src_lang)

    #         translated_lines.append(f"{key}{colon}{translated_val}")

    #     final_text = "\n".join(translated_lines)


        # 多言語対応（店名は翻訳しない）
        if not src_lang.startswith("zh"):
            name_line = next((l for l in lines if l.startswith("店名：")), None)
            other_lines = [l for l in lines if not l.startswith("店名：")]
            translated = _translate("\n".join(other_lines), src_lang)
            final_text = "\n".join(filter(None, [name_line, translated]))

        results.append({
            "text": final_text.strip(),
            "photo_url": matched_photo
        })

        if len(results) >= 3:
            break

    return results



# def answer_ramen(query: str, metadata_filters: Optional[Dict[str, Any]] = None) -> List[dict]:
#     from langchain.docstore.document import Document

#     src_lang = detect(query)
#     zh_query = query if src_lang.startswith("zh") else _translate(query, 'zh')

#     # 地名 → 座標取得
#     address = extract_address(query)
#     query_coord = geocode_location(address) if address else None

#     # FAISS検索（10件）
#     docs = _vectorstore.similarity_search(zh_query, k=10)

#     # 距離補正：近い順に並び替え
#     if query_coord:
#         def dist(doc):
#             loc = doc.metadata.get("location")
#             if loc:
#                 return geodesic(query_coord, (loc["lat"], loc["lng"])).meters
#             return float("inf")
#         docs.sort(key=dist)

#     # チェーン初期化して回答取得
#     _init_qa_chain(filters=metadata_filters)
#     raw = _qa_chain.invoke({"query": zh_query}).get("result", "")
#     blocks = [b.strip() for b in raw.strip().split('---') if b.strip()]

#     results = []
#     for block in blocks:
#         processed = _post_process(block)

#         # 店名
#         store_name = None
#         for line in processed.splitlines():
#             if line.startswith("店名："):
#                 store_name = line.replace("店名：", "").strip()
#                 break

#         # メタ一致
#         matched_url = "N/A"
#         matched_photo = ""
#         matched_rating = None
#         matched_reviews = None
#         if store_name:
#             for doc in docs:
#                 title = doc.metadata.get("title", "")
#                 if store_name in title:
#                     matched_url    = doc.metadata.get("maps_url", "N/A")
#                     matched_photo  = doc.metadata.get("photo_url", "")
#                     matched_rating = doc.metadata.get("rating", None)
#                     matched_reviews= doc.metadata.get("reviews_count", None)
#                     break

#         # 評価行を作る
#         rating_line = None
#         if matched_rating is not None:
#             try:
#                 r = float(matched_rating)
#                 full_stars = max(0, min(5, int(round(r))))
#                 star_str = "★" * full_stars + "☆" * (5 - full_stars)
#                 if isinstance(matched_reviews, int):
#                     rating_line = f"評價：{star_str} {r:.1f}（{matched_reviews:,}）"
#                 else:
#                     rating_line = f"評價：{star_str} {r:.1f}"
#             except Exception:
#                 pass

#         # ここで必ず最新の lines を組み立て直す
#         lines = processed.splitlines()

#         # 店名直下に 評價 行を差し込む
#         if rating_line:
#             for i, l in enumerate(lines):
#                 if l.startswith("店名："):
#                     lines.insert(i + 1, rating_line)
#                     break

#         # Link 行は最後に1本だけ
#         lines = [l for l in lines if not l.startswith("Link：")]
#         lines.append(f"Link：{matched_url}")

#         final_text = "\n".join(lines)

#         # 多言語対応（店名は翻訳しない）
#         if not src_lang.startswith("zh"):
#             name_line = next((l for l in lines if l.startswith("店名：")), None)
#             other_lines = [l for l in lines if not l.startswith("店名：")]
#             translated = _translate("\n".join(other_lines), src_lang)
#             final_text = "\n".join(filter(None, [name_line, translated]))

#         results.append({
#             "text": final_text.strip(),
#             "photo_url": matched_photo
#         })

#         if len(results) >= 3:
#             break

#     return results

# def answer_ramen(query: str, metadata_filters: Optional[Dict[str, Any]] = None) -> List[dict]:
#     from langchain.docstore.document import Document

#     src_lang = detect(query)
#     zh_query = query if src_lang.startswith("zh") else _translate(query, 'zh')

#     # 地名 → 座標取得
#     address = extract_address(query)
#     query_coord = geocode_location(address) if address else None

#     # FAISS検索（10件）
#     docs = _vectorstore.similarity_search(zh_query, k=10)

#     # 距離補正：近い順に並び替え
#     if query_coord:
#         def dist(doc):
#             loc = doc.metadata.get("location")
#             if loc:
#                 return geodesic(query_coord, (loc["lat"], loc["lng"])).meters
#             return float("inf")
#         docs.sort(key=dist)

#     # チェーン初期化して回答取得
#     _init_qa_chain(filters=metadata_filters)
#     raw = _qa_chain.invoke({"query": zh_query}).get("result", "")
#     blocks = raw.strip().split('---')

#     results = []
#     for block in blocks:
#         block = block.strip()
#         if not block:
#             continue
#         processed = _post_process(block)

#         store_name = None
#         for line in processed.splitlines():
#             if line.startswith("店名："):
#                 store_name = line.replace("店名：", "").strip()
#                 break

#         matched_url = "N/A"
#         matched_photo = ""
#         # matched_rating = None
#         # matched_reviews = None

#         # if store_name:
#         #     for doc in docs:
#         #         if store_name in doc.metadata.get("title", ""):
#         #             matched_url = doc.metadata.get("maps_url", "N/A")
#         #             matched_photo = doc.metadata.get("photo_url", "")
#         #             matched_rating = doc.metadata.get("rating", None)
#         #             matched_reviews = doc.metadata.get("reviews_count", None)
#         #             break

#         lines = processed.splitlines()

#         # # ⭐ 評価を店名直下に挿入（星＋数値＋件数）
#         # if matched_rating is not None:
#         #     try:
#         #         r = float(matched_rating)
#         #         full_stars = int(round(r))  # 4.2 -> 4
#         #         full_stars = max(0, min(full_stars, 5))
#         #         star_str = "★" * full_stars + "☆" * (5 - full_stars)
#         #         if isinstance(matched_reviews, int):
#         #             rating_line = f"評價：{star_str} {r:.1f}（{matched_reviews:,}）"
#         #         else:
#         #             rating_line = f"評價：{star_str} {r:.1f}"
#         #         # 店名行の直後に差し込む
#         #         for i, l in enumerate(lines):
#         #             if l.startswith("店名："):
#         #                 lines.insert(i + 1, rating_line)
#         #                 break
#         #     except Exception:
#         #         pass  # rating が変でも落ちないように

#         # # Link を再構成（既存の Link 行は消して最後に追加）
#         # lines = [line for line in lines if not line.startswith("Link：")]
#         # lines.append(f"Link：{matched_url}")
#         # ramen_qa.py 内、results.append する前に追加する処理
#         if store_name:
#             for doc in docs:
#                 if store_name in doc.metadata.get("title", ""):
#                     matched_url = doc.metadata.get("maps_url", "N/A")
#                     matched_photo = doc.metadata.get("photo_url", "")
#                     rating = doc.metadata.get("rating", None)
#                     reviews = doc.metadata.get("reviews_count", None)

#                     # 評価を星付きで作成
#                     if rating is not None:
#                         full_stars = int(round(rating))
#                         full_stars = max(0, min(full_stars, 5))
#                         star_str = "★" * full_stars + "☆" * (5 - full_stars)
#                         if isinstance(reviews, int):
#                             rating_str = f"{star_str} {rating:.1f}（{reviews:,}）"
#                         else:
#                             rating_str = f"{star_str} {rating:.1f}"
#                         processed += f"\n評價：{rating_str}"
#                     break

#         final_text = "\n".join(lines)

#         # 必要なら多言語に戻す（店名は原語のまま）
#         if not src_lang.startswith("zh"):
#             name_line = next((l for l in lines if l.startswith("店名：")), None)
#             other_lines = [l for l in lines if not l.startswith("店名：")]
#             translated = _translate("\n".join(other_lines), src_lang)
#             final_text = "\n".join(filter(None, [name_line, translated]))

#         results.append({
#             "text": final_text.strip(),
#             "photo_url": matched_photo
#         })

#         if len(results) >= 3:
#             break

#     return results
# def answer_ramen(query: str, metadata_filters: Optional[Dict[str, Any]] = None) -> List[dict]:
#     from langchain.docstore.document import Document

#     src_lang = detect(query)
#     zh_query = query if src_lang.startswith("zh") else _translate(query, 'zh')

#     # 地名 → 座標取得
#     address = extract_address(query)
#     query_coord = geocode_location(address) if address else None

#     # FAISS検索（10件）
#     docs = _vectorstore.similarity_search(zh_query, k=10)

#     # 距離補正：近い順に並び替え
#     if query_coord:
#         def dist(doc):
#             loc = doc.metadata.get("location")
#             if loc:
#                 return geodesic(query_coord, (loc["lat"], loc["lng"])).meters
#             return float("inf")
#         docs.sort(key=dist)

#     # チェーン初期化して回答取得
#     _init_qa_chain(filters=metadata_filters)
#     raw = _qa_chain.invoke({"query": zh_query}).get("result", "")
#     blocks = raw.strip().split('---')

#     results = []
#     for block in blocks:
#         block = block.strip()
#         if not block:
#             continue
#         processed = _post_process(block)

#         store_name = None
#         for line in processed.splitlines():
#             if line.startswith("店名："):
#                 store_name = line.replace("店名：", "").strip()
#                 break

#         matched_url = "N/A"
#         matched_photo = ""
#         matched_rating = None
#         matched_reviews = None

#         if store_name:
#             for doc in docs:
#                 if store_name in doc.metadata.get("title", ""):
#                     matched_url = doc.metadata.get("maps_url", "N/A")
#                     matched_photo = doc.metadata.get("photo_url", "")
#                     matched_rating = doc.metadata.get("rating", None)
#                     matched_reviews = doc.metadata.get("reviews_count", None)
#                     break

#         lines = processed.splitlines()

#         # ⭐ 評価を店名直下に挿入
#         if matched_rating is not None:
#             try:
#                 r = float(matched_rating)
#                 full_stars = int(round(r))  # 四捨五入
#                 full_stars = max(0, min(full_stars, 5))
#                 star_str = "★" * full_stars + "☆" * (5 - full_stars)
#                 if isinstance(matched_reviews, int):
#                     rating_line = f"評價：{star_str} {r:.1f}（{matched_reviews:,}）"
#                 else:
#                     rating_line = f"評價：{star_str} {r:.1f}"
#                 for i, l in enumerate(lines):
#                     if l.startswith("店名："):
#                         lines.insert(i + 1, rating_line)
#                         break
#             except Exception:
#                 pass

#         # Link を最後に追加（既存の Link は削除）
#         lines = [line for line in lines if not line.startswith("Link：")]
#         lines.append(f"Link：{matched_url}")

#         final_text = "\n".join(lines)

#         # 多言語対応
#         if not src_lang.startswith("zh"):
#             name_line = next((l for l in lines if l.startswith("店名：")), None)
#             other_lines = [l for l in lines if not l.startswith("店名：")]
#             translated = _translate("\n".join(other_lines), src_lang)
#             final_text = "\n".join(filter(None, [name_line, translated]))

#         results.append({
#             "text": final_text.strip(),
#             "photo_url": matched_photo
#         })

#         if len(results) >= 3:
#             break

#     return results



# ───────────────────────────────────────
# ヘルパー：翻訳
# ───────────────────────────────────────
def _translate(text: str, target_lang: str) -> str:
    if target_lang == 'zh':
        prompt = f"请将以下文字翻译成简体中文：\n\n{text}"
    elif target_lang == 'ja':
        prompt = f"请将以下简体中文翻译成日语：\n\n{text}"
    elif target_lang == 'en':
        prompt = f"请将以下简体中文翻译成英语：\n\n{text}"
    else:
        return text
    return _llm.invoke(prompt).content.strip()

# ───────────────────────────────────────
# ヘルパー：整形
# ───────────────────────────────────────
def _post_process(response: str) -> str:
    lines = []
    for line in response.splitlines():
        if "：" not in line:
            continue
        key, _, val = line.partition("：")
        val = val.strip()
        if key == "地址":
            val = re.sub(r'^\d{3,6}\s*', '', val)
        lines.append(f"{key}：{val}")
    return "\n".join(lines)
