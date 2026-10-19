
from pinecone_client import get_pinecone_index

TEST_NAMESPACE = "rag-test"


# テスト用の記憶をPineconeに登録する関数
def register_test_memory(index):
    records = [
        {
            "_id": "test-selection-001",
            "text": (
                "ニュース：企業で生成AIの導入が進んでいる。"
                "ユーザーはAIによる業務効率化や、"
                "人間の意思決定に関するニュースを選択した。"
            ),
            "user_id": "test-user",
            "memory_type": "selection",
            "news_id": "test-news-001",
        }
    ]

    index.upsert_records(
        namespace=TEST_NAMESPACE,
        records=records,
    )

    print("テスト用の記憶を登録しました。")


# 意味の近い記憶を検索する関数
def search_test_memory(index):
    result = index.search(
        namespace=TEST_NAMESPACE,
        query={
            "inputs": {
                "text": "AIと人間の仕事の役割について"
            },
            "top_k": 3,
            "filter": {
                "user_id": {"$eq": "test-user"}
            },
        },
        fields=["text", "user_id", "memory_type"],
    )

    print("\n検索結果:")
    print(result)


# 登録と検索を実行する関数
def main():
    index = get_pinecone_index()

    register_test_memory(index)
    search_test_memory(index)


if __name__ == "__main__":
    main()
