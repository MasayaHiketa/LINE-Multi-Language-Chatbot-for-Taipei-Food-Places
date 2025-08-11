# # add_reviews_to_faiss.py

import os
import json
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.faiss import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

INDEX_PATH = "faiss_index"
JSON_FILE  = "ramen_google_reviews.json"
BATCH_SIZE = 100  # 1回で投げる件数

def main():
    # 1) JSON 読み込み
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        entries = json.load(f)

    docs = []
    for e in entries:
        content = e.get("text", "")
        metadata = e["metadata"].copy()
        metadata["title"] = e["title"]
        metadata["url"]   = e["url"]
        metadata["photo_url"] = metadata.get("photo_url", None)
        docs.append(Document(page_content=content, metadata=metadata))

    # 2) チャンクに分割
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    augmented_chunks = []
    for chunk in chunks:
        md = chunk.metadata
        weekday_list = md.get("opening_hours", {}).get("weekday_text", [])
        opening = "; ".join(weekday_list) if weekday_list else "無資料"

        fields = {
            "標題": md.get("title", ""),
            "地址": md.get("address", ""),
            "價格": md.get("price_range", ""),
            "捷運站": ",".join(md.get("mrt_stations", [])),
            "公車站": ",".join(md.get("bus_stations", [])),
            "營業時間": opening,
        }

        lines = []
        for key, val in fields.items():
            if not val or val in ("無", "無資料"):
                continue
            if key == "GoogleMap" and not val.lower().startswith("http"):
                continue
            lines.append(f"{key}：{val}")

        header = "\n".join(lines) + "\n\n"
        new_content = header + chunk.page_content
        augmented_chunks.append(
            Document(page_content=new_content, metadata=md)
        )

    # 3) 埋め込みモデル
    embedding = OpenAIEmbeddings()

    # 4) インデックスのロード or 新規作成
    if os.path.isdir(INDEX_PATH) and os.path.exists(os.path.join(INDEX_PATH, "index.faiss")):
        vectorstore = FAISS.load_local(
            INDEX_PATH,
            embedding,
            allow_dangerous_deserialization=True
        )
        print(f"✅ Loaded existing index.")
    else:
        # 最初のBATCHだけで新規作成
        first_batch = augmented_chunks[:BATCH_SIZE]
        vectorstore = FAISS.from_documents(first_batch, embedding)
        os.makedirs(INDEX_PATH, exist_ok=True)
        print(f"✅ Created new index with {len(first_batch)} chunks.")
        augmented_chunks = augmented_chunks[BATCH_SIZE:]

    # 5) 残りを分割追加
    for i in range(0, len(augmented_chunks), BATCH_SIZE):
        batch = augmented_chunks[i:i + BATCH_SIZE]
        vectorstore.add_documents(batch)
        print(f"✅ Added batch {i//BATCH_SIZE + 1} ({len(batch)} chunks)")

    # 6) 保存
    vectorstore.save_local(INDEX_PATH)
    print(f"✅ FAISS index saved at '{INDEX_PATH}'.")

if __name__ == "__main__":
    main()





# import os
# import json
# from langchain_openai import OpenAIEmbeddings
# from langchain_community.vectorstores.faiss import FAISS
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.schema import Document
# from langchain.schema import Document
# INDEX_PATH = "faiss_index"
# JSON_FILE  = "ramen_google_reviews.json"

# def main():
#     # 1) JSON 読み込み
#     with open(JSON_FILE, "r", encoding="utf-8") as f:
#         entries = json.load(f)

#     docs = []
#     for e in entries:
#         # 本文だけを page_content に入れる
#         content = e.get("text", "")
#         # metadata はそのまま
#         metadata = e["metadata"].copy()
#         metadata["title"] = e["title"]
#         metadata["url"]   = e["url"]
#         # 念のため photo_url がなければ None を補う
#         metadata["photo_url"] = metadata.get("photo_url", None)
#         docs.append(Document(page_content=content, metadata=metadata))

#     # ① チャンクに分割
#     splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
#     chunks = splitter.split_documents(docs)

#     augmented_chunks = []
#     for chunk in chunks:
#         md = chunk.metadata
#         weekday_list = md.get("opening_hours", {}).get("weekday_text", [])
#         opening = "; ".join(weekday_list) if weekday_list else "無資料"

#         # 各フィールドを dict でまとめる
#         fields = {
#             "標題": md.get("title", ""),
#             "地址": md.get("address", ""),
#             "價格": md.get("price_range", ""),
#             "捷運站": ",".join(md.get("mrt_stations", [])),
#             "公車站": ",".join(md.get("bus_stations", [])),
#             "營業時間": opening,
#             #"GoogleMap": md.get("maps_url", ""),
#             #"URL": md.get("url", ""),
#         }

#         # 空文字／無資料 を省きつつ、URL系だけはクオートで包む
#         lines = []
#         for key, val in fields.items():
#             if not val or val in ("無", "無資料"):
#                 continue
#             if key in ("GoogleMap"):
#                 if not val.lower().startswith("http"):
#                     continue
#                 val = f'"{val}"'
#             lines.append(f"{key}：{val}")

#         header = "\n".join(lines) + "\n\n"
#         new_content = header + chunk.page_content
#         augmented_chunks.append(
#             Document(page_content=new_content, metadata=md)
#         )

#     # 3) 埋め込みモデル
#     embedding = OpenAIEmbeddings()

#     # 4) インデックスのロード or 新規作成
#     if os.path.isdir(INDEX_PATH) and os.path.exists(os.path.join(INDEX_PATH, "index.faiss")):
#         # 既存インデックスをロードして追加
#         vectorstore = FAISS.load_local(
#             INDEX_PATH,
#             embedding,
#             allow_dangerous_deserialization=True
#         )
#         vectorstore.add_documents(augmented_chunks)
#         print(f"✅ Loaded existing index, added {len(augmented_chunks)} augmented_chunks.")
#     else:
#         # 新規インデックス作成
#         vectorstore = FAISS.from_documents(augmented_chunks, embedding)
#         os.makedirs(INDEX_PATH, exist_ok=True)
#         print(f"✅ Created new index with {len(augmented_chunks)} augmented_chunks.")

#     # 5) 保存
#     vectorstore.save_local(INDEX_PATH)
#     print(f"✅ FAISS index saved at '{INDEX_PATH}'.")

# if __name__ == "__main__":
#     main()
