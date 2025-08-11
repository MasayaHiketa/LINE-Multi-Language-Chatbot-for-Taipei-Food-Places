# rebuild_index.py

import json
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.faiss import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

# 全記事JSONを読み込む
with open("ramen_taipei_full.json", "r", encoding="utf-8") as f:
    all_data = json.load(f)

# Document化＋チャンク分割
docs = []
for e in all_data:
    docs.append(Document(
        page_content=f"{e['title']}\n{e['text']}",
        metadata={k: e[k] for k in ["title","url","area","genre","date"]}
    ))

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(docs)

# 新規インデックス作成
embedding = OpenAIEmbeddings()
vectorstore = FAISS.from_documents(chunks, embedding)

# 保存
vectorstore.save_local("faiss_index")
print("✅ 全件再構築しました。")
