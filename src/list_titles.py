"""登録済み（論理削除されていない）記事のタイトル一覧と、ジャンル別の記事数を表示する。

ジャンル別の記事数には config/settings.toml の genres のうち未使用（0件）のものも含める。
"""

from collections import Counter

from sqlalchemy import select

from db import get_sessionmaker
from models import EnglishText
from settings import load_settings


def main() -> None:
    with get_sessionmaker()() as session:
        rows = session.execute(
            select(EnglishText.title, EnglishText.level, EnglishText.genre)
            .where(EnglishText.is_deleted.is_(False))
            .order_by(EnglishText.id)
        ).all()

    print("## titles")
    for title, level, genre in rows:
        print(f"[{level}] [{genre}] {title}")
    print(f"total: {len(rows)}")

    counts = Counter(genre for _, _, genre in rows)
    for genre in load_settings().get("generation", {}).get("genres", []):
        counts.setdefault(genre, 0)
    print("\n## articles per genre (少ない順)")
    for genre, count in sorted(counts.items(), key=lambda item: (item[1], item[0])):
        print(f"{genre}: {count}")


if __name__ == "__main__":
    main()
