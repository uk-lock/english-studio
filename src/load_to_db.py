"""text.md と翻訳済みの sentences.csv を検証し、english_texts / sentences へ登録する。

同じタイトルの記事（論理削除済みを除く）が既にあれば登録を拒否する。登録後の記事は
単語帳の sentence_ids から参照されるため、上書き・再登録はしない。

使い方: python src/load_to_db.py intermediate/<slug> [--dry-run]
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from article import count_words, read_article, read_sentences
from db import get_sessionmaker
from models import EnglishText, Sentence


def validate(article_dir: Path) -> list[str]:
    article = read_article(article_dir)
    rows = read_sentences(article_dir)
    errors = []

    orders = [row["order_no"] for row in rows]
    if orders != list(range(1, len(rows) + 1)):
        errors.append("order_no が1始まりの連番になっていません")
    paragraphs = sorted({row["paragraph_no"] for row in rows})
    if paragraphs != list(range(1, len(article.paragraphs) + 1)):
        errors.append("paragraph_no が text.md の段落数と一致しません")
    else:
        for no, paragraph in enumerate(article.paragraphs, start=1):
            joined = " ".join(row["english"] for row in rows if row["paragraph_no"] == no)
            if joined.split() != paragraph.split():
                errors.append(f"段落{no}の english が text.md と一致しません")
    for row in rows:
        if not row["english"].strip():
            errors.append(f"order_no={row['order_no']}: english が空です")
        if not row["japanese"].strip():
            errors.append(f"order_no={row['order_no']}: japanese が空です")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article_dir", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="検証のみ行いDBへは接続しない")
    args = parser.parse_args()

    errors = validate(args.article_dir)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    article = read_article(args.article_dir)
    rows = read_sentences(args.article_dir)
    word_count = count_words(article.english_text)
    print(
        f"title: {article.title} / level: {article.level} / genre: {article.genre}"
        f" / word_count: {word_count}"
    )
    print(f"sentences: {len(rows)}")
    if args.dry_run:
        print("dry-run: 検証OK（DBへは登録していません）")
        return 0

    with get_sessionmaker()() as session:
        exists = session.scalar(
            select(EnglishText.id).where(
                EnglishText.title == article.title, EnglishText.is_deleted.is_(False)
            )
        )
        if exists is not None:
            print(f"error: 同じタイトルの記事が登録済みです（id={exists}）", file=sys.stderr)
            return 1

        text = EnglishText(
            title=article.title,
            level=article.level,
            genre=article.genre,
            english_text=article.english_text,
            word_count=word_count,
        )
        text.sentences = [
            Sentence(
                order_no=row["order_no"],
                paragraph_no=row["paragraph_no"],
                english=row["english"],
                japanese=row["japanese"],
            )
            for row in rows
        ]
        session.add(text)
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            print(f"error: 登録に失敗しました（タイトル重複の可能性）: {e.orig}", file=sys.stderr)
            return 1
        saved = session.scalar(
            select(Sentence.id).where(Sentence.text_id == text.id).order_by(Sentence.id.desc())
        )
        print(f"registered: english_texts.id={text.id}, last sentences.id={saved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
