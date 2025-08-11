# add_entries_to_faiss.py

import json
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.faiss import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

def main():
    # 1) parsed_entries.json 読み込み
    with open("parsed_entries.json", "r", encoding="utf-8") as f:
        entries = json.load(f)

    # 2) Document化＋チャンク分割
    docs = []
    for e in entries:
        docs.append(Document(
            page_content=f"{e['title']}\n{e['text']}",
            metadata={"title": e["title"], "url": e["url"]}
        ))
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    # 3) FAISS インデックスをロード＆追加
    embedding = OpenAIEmbeddings()
    vectorstore = FAISS.load_local(
        "faiss_index",
        embedding,
        allow_dangerous_deserialization=True
    )
    vectorstore.add_documents(chunks)

    # 4) 保存
    vectorstore.save_local("faiss_index")
    print(f"✅ Added {len(chunks)} chunks to faiss_index")

if __name__ == "__main__":
    main()
