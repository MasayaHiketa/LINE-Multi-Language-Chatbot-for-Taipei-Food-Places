# inspect_faiss.py

from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores.faiss import FAISS

# 1. 埋め込みモデル初期化
embedding = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

# 2. インデックス読み込み（自分が作成したインデックスなので安全とみなし許可）
vectorstore = FAISS.load_local(
    "faiss_index", 
    embedding, 
    allow_dangerous_deserialization=True
)

# 3. 登録ベクトル数を表示
print("Total vectors:", vectorstore.index.ntotal)

# 4. 内部ドキュメントを取り出して確認
#    docstore._dict に Document オブジェクトが格納されています
docs = list(vectorstore.docstore._dict.values())
for i, doc in enumerate(docs[:3], 1):
    print(f"\n--- Doc {i} ---")
    print("Text:", doc.page_content)
    print("Metadata:", doc.metadata)


print(f"\n------")
# ベクトルとメタデータを一緒に表示
vector = vectorstore.index.reconstruct(0)  # 最初のベクトルを取得
print("First vector:", vector)