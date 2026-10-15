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


if __name__ == "__main__":
    test_connection()