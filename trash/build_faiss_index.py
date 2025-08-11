import json
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
import os

# JSONデータの読み込み
with open("data/ramen_taipei.json", "r", encoding="utf-8") as f:
    raw_data = json.load(f)

# Documentリストの作成
docs = []
for entry in raw_data:
    content = f"{entry['title']}\n{entry['text']}"
    metadata = {
        "title": entry["title"],
        "url": entry["url"],
        "area": entry["area"],
        "genre": entry["genre"],
        "date": entry["date"]
    }
    docs.append(Document(page_content=content, metadata=metadata))

# テキストを分割
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
split_docs = text_splitter.split_documents(docs)

# OpenAI埋め込みモデル
embedding = OpenAIEmbeddings()

# FAISSにインデックス化
faiss_index = FAISS.from_documents(split_docs, embedding)

# 保存
faiss_index.save_local("faiss_index")
print("✅ FAISS index saved to ./faiss_index/")
