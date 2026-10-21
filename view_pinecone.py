
from pinecone_client import get_pinecone_index


# Pineconeに保存されている全レコードを一覧表示する関数
def view_all_memories(target_user_id):
    index = get_pinecone_index()
    namespace = target_user_id

    count = 0

    for id_batch in index.list(namespace=namespace):

        # ListItemからレコードIDの文字列を取り出す
        record_ids = [item.id for item in id_batch]

        # IDを使ってレコードの内容を取得する
        response = index.fetch(
            ids=record_ids,
            namespace=namespace,
        )

        for record_id, record in response.vectors.items():
            count += 1
            metadata = record.metadata or {}

            print("\n" + "=" * 70)
            print(f"レコード番号：{count}")
            print(f"ID：{record_id}")
            print(f"ユーザーID：{metadata.get('user_id', '')}")
            print(f"記憶の種類：{metadata.get('memory_type', '')}")
            print(f"セッションID：{metadata.get('session_id', '')}")
            print(f"非選択：{metadata.get('none_selected', '')}")

            print("\n【検索用テキスト】")
            print(metadata.get("text", ""))

            print("\n【提示された記事タイトル】")
            for i, title in enumerate(
                metadata.get("presented_titles", []), start=1
            ):
                print(f"{i}. {title}")

    print("\n" + "=" * 70)
    print(f"登録レコード総数：{count}")


if __name__ == "__main__":
    user_id = input("確認したいユーザーIDを入力してください：")
    view_all_memories(target_user_id=user_id)
