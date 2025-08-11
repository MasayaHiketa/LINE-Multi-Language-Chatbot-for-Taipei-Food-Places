# ramen_qa.py

import os
import re
from typing import Optional, Dict, Any
from langchain_openai import OpenAIEmbeddings
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from langchain_community.vectorstores.faiss import FAISS
from langchain.prompts import PromptTemplate
from typing import Optional, Dict, Any
from langdetect import detect
# 環境変数からキー取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Please set OPENAI_API_KEY environment variable")

# 埋め込みモデルとインデックスパス設定
_embedding = OpenAIEmbeddings()
_INDEX_PATH = "faiss_index"

# FAISSインデックスをロードまたはNone初期化
try:
    _vectorstore = FAISS.load_local(
        _INDEX_PATH,
        _embedding,
        allow_dangerous_deserialization=True
    )
except Exception:
    _vectorstore = None

# チャットモデル
_llm = ChatOpenAI(model="gpt-3.5-turbo")
_qa_chain: Optional[RetrievalQA] = None


QA_PROMPT = PromptTemplate(
    template="""\
您是台北的拉麵導覽 AI，請根據以下參考資料，對提問做出簡潔且具體的回答。
**請優先考慮「問題中提及的地點」與「捷運站」欄位最接近的店家，最多給出3家。**

請僅以以下格式，每家店之間以 `---` 分隔，並不要加入其他說明文字或語句。

問題：
{question}

參考資料：
{context}

輸出格式（最多三家）：

店名：  
地址：   
價格：  
推薦：  
特色：
營業時間:

---
店名：  
地址：    
價格：  
推薦：  
特色：
營業時間:

---
店名：  
地址：    
價格：  
推薦：  
特色：
營業時間:
""",
    input_variables=["context", "question"]
)



def _init_qa_chain(filters: Optional[Dict[str, Any]] = None):
    global _qa_chain
    if _qa_chain is None or filters is not None:
        if _vectorstore is None:
            raise RuntimeError(
                f"FAISS index not found at '{_INDEX_PATH}'. Please create or update the index using build_or_update_faiss_index.py."
            )
        retriever = _vectorstore.as_retriever(
            search_kwargs={
                "filter": filters or {},
                "k": 5  # 検索上位5件を利用
            }
        )
        # カスタムプロンプトを使った RetrievalQA の定義
        _qa_chain = RetrievalQA.from_chain_type(
            llm=_llm,
            retriever=retriever,
            chain_type="stuff",
            chain_type_kwargs={"prompt": QA_PROMPT}
        )


import re
from typing import Optional, Dict, Any

def _post_process(response: str) -> str:
    lines = []
    for line in response.splitlines():
        if "：" not in line:
            continue
        key, _, val = line.partition("：")
        val = val.strip()

        # 地址欄の郵遞區號削除
        if key == "地址":
            val = re.sub(r'^\d{3,6}\s*', '', val)

        # 圖片のURLはそのまま保持（もしくはURL形式のみ許可しても可）
        if key == "圖片" and not val.lower().startswith("http"):
            continue

        lines.append(f"{key}：{val}")

    return "\n".join(lines)


def _translate(text: str, target_lang: str) -> str:
    """
    target_lang: 'zh'（簡体中文）、'ja'（日本語）、'en'（英語）など
    """
    if target_lang == 'zh':
        prompt = f"请将以下文字翻译成简体中文：\n\n{text}"
    elif target_lang == 'ja':
        prompt = f"请将以下简体中文翻译成日语：\n\n{text}"
    elif target_lang == 'en':
        prompt = f"请将以下简体中文翻译成英语：\n\n{text}"
    else:
        return text
    return _llm.predict(prompt).strip()

def answer_ramen(query: str, metadata_filters: Optional[Dict[str, Any]] = None) -> list[dict]:
    from langchain.docstore.document import Document
    src_lang = detect(query)
    zh_query = query if src_lang.startswith("zh") else _translate(query, 'zh')

    _init_qa_chain(filters=metadata_filters)
    raw = _qa_chain.invoke({"query": zh_query}).get("result", "")
    blocks = raw.strip().split('---')

    docs = _vectorstore.similarity_search(zh_query, k=10)

    results = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        processed = _post_process(block)

        store_name = None
        for line in processed.splitlines():
            if line.startswith("店名："):
                store_name = line.replace("店名：", "").strip()
                break

        matched_maps_url = "N/A"
        matched_photo_url = ""
        if store_name:
            for doc in docs:
                title = doc.metadata.get("title", "")
                if store_name in title:
                    matched_maps_url = doc.metadata.get("maps_url", "N/A")
                    matched_photo_url = doc.metadata.get("photo_url", "")
                    break

        lines = processed.splitlines()
        lines = [line for line in lines if not line.startswith("Link：")]
        lines.append(f"Link：{matched_maps_url}")
        final_text = "\n".join(lines)

        if not src_lang.startswith("zh"):
            name_line = next((l for l in lines if l.startswith("店名：")), None)
            other_lines = [l for l in lines if not l.startswith("店名：")]
            translated = _translate("\n".join(other_lines), src_lang)
            final_text = "\n".join(filter(None, [name_line, translated]))

        results.append({
            "text": final_text.strip(),
            "photo_url": matched_photo_url
        })

        if len(results) >= 3:
            break

    return results


# def answer_ramen(query: str, metadata_filters: Optional[Dict[str, Any]] = None) -> str:
#     # 1) クエリを中国語（簡体）に翻訳
#     src_lang = detect(query)
#     zh_query = query if src_lang.startswith("zh") else _translate(query, 'zh')

#     # 2) QA 実行
#     _init_qa_chain(filters=metadata_filters)
#     raw = _qa_chain.invoke({"query": zh_query}).get("result", "")
#     blocks = raw.strip().split('---')

#     # 3) ドキュメント群を取得（metadata参照用）
#     docs = _vectorstore.similarity_search(zh_query, k=10)

#     results = []
#     for block in blocks:
#         block = block.strip()
#         if not block:
#             continue

#         processed = _post_process(block)

#         # 4) 店名抽出して metadata から URL 補完
#         store_name = None
#         for line in processed.splitlines():
#             if line.startswith("店名："):
#                 store_name = line.replace("店名：", "").strip()
#                 break

#         matched_url = "N/A"
#         if store_name:
#             for doc in docs:
#                 title = doc.metadata.get("title", "")
#                 if store_name in title:
#                     matched_url = doc.metadata.get("maps_url", "N/A")
#                     break

#         # 5) 最後に Link 行を追加
#         final_text = processed + f"\nLink：{matched_url}"

#         # 6) 多言語翻訳：店名以外を翻訳
#         if not src_lang.startswith("zh"):
#             lines = final_text.splitlines()
#             name_line = next((l for l in lines if l.startswith("店名：")), None)
#             other_lines = [l for l in lines if not l.startswith("店名：")]
#             translated = _translate("\n".join(other_lines), src_lang)
#             final = "\n".join(filter(None, [name_line, translated]))
#         else:
#             final = final_text

#         results.append(final.strip())

#         if len(results) >= 3:
#             break

#     return "\n---\n".join(results)

# def answer_ramen(query: str, metadata_filters: Optional[Dict[str, Any]] = None) -> str:
#     # 1) クエリを中国語（簡体）に翻訳
#     src_lang = detect(query)
#     zh_query = query if src_lang.startswith("zh") else _translate(query, 'zh')

#     # 2) QA 実行
#     _init_qa_chain(filters=metadata_filters)
#     raw = _qa_chain.invoke({"query": zh_query}).get("result", "")
#     # 複数店舗分の raw を取得したと仮定（--- 区切り）
#     blocks = raw.strip().split('---')

#     results = []
#     for block in blocks:
#         block = block.strip()
#         if not block:
#             continue
#         processed = _post_process(block)  # 鍵：値 に整形（すでにされていればスキップ可）

#         # 3) 多言語翻訳：店名は翻訳せず、それ以外を翻訳
#         if not src_lang.startswith("zh"):
#             lines = processed.splitlines()
#             name_line = next((l for l in lines if l.startswith("店名：")), None)
#             other_lines = [l for l in lines if not l.startswith("店名：")]
#             translated = _translate("\n".join(other_lines), src_lang)
#             final = "\n".join(filter(None, [name_line, translated]))
#         else:
#             final = processed

#         results.append(final.strip())

#         # 最大3件まで
#         if len(results) >= 3:
#             break

#     return "\n---\n".join(results)








