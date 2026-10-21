
import os
from dotenv import load_dotenv
from pinecone import Pinecone

# .envから環境変数を読み込む
load_dotenv()


# Pineconeに接続する関数
def get_pinecone_index():
    api_key = os.getenv("PINECONE_API_KEY")

    if not api_key:
        raise ValueError("PINECONE_API_KEYが設定されていません")

    client = Pinecone(api_key=api_key)
    index = client.Index("news-revision-memory")

    return index


# Pineconeへの接続を確認する関数
def test_connection():
    index = get_pinecone_index()

    stats = index.describe_index_stats()

    print("Pineconeへの接続に成功しました")
    print("登録レコード数:", stats.total_vector_count)



# ユーザーの記憶とメタデータをPineconeに登録する関数
def save_memory(memory_id, user_id, memory_type, text, metadata=None):
    index = get_pinecone_index()

    # 検索用テキストと基本情報を設定する
    record = {
        "_id": memory_id,
        "text": text,
        "user_id": user_id,
        "memory_type": memory_type,
    }

    # 追加のメタデータがあれば登録する
    if metadata is not None:
        for key, value in metadata.items():
            if key in record:
                raise ValueError(f"予約済みの項目は上書きできません: {key}")
            record[key] = value

    index.upsert_records(
    namespace=user_id,
    records=[record],
)



# 指定ユーザーの記憶をPineconeから検索する関数
def search_memories(user_id, query_text, memory_type=None, top_k=5):
    index = get_pinecone_index()

    # 記憶の種類を指定された場合は絞り込む
    search_filter = {}

    if memory_type is not None:
        search_filter["memory_type"] = {"$eq": memory_type}

    # 検索条件を作成する
    query = {
        "inputs": {"text": query_text},
        "top_k": top_k,
    }

    if search_filter:
        query["filter"] = search_filter

    # ユーザー専用Namespaceから検索する
    results = index.search(
        namespace=user_id,
        query=query,
        fields=["text", "user_id", "memory_type"],
    )

    return results


if __name__ == "__main__":
    test_connection()


