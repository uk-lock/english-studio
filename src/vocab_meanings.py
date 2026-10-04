"""単語帳の意味補完。

pending: meaning が NULL の単語（論理削除済みを除く）を JSON 配列で出力する
apply:   {"<word>": "<意味>", ...} の JSON を、meaning が NULL のままの単語にだけ反映する

使い方:
    python src/vocab_meanings.py pending [--output <JSONのパス>]
    python src/vocab_meanings.py apply <JSONのパス>
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select, update

from db import get_sessionmaker
from models import VocabularyNotebook


def pending(output: Path | None) -> int:
    with get_sessionmaker()() as session:
        words = session.scalars(
            select(VocabularyNotebook.word)
            .where(VocabularyNotebook.meaning.is_(None), VocabularyNotebook.is_deleted.is_(False))
            .order_by(VocabularyNotebook.id)
        ).all()
    payload = json.dumps(list(words), ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
        print(f"pending: {len(words)} -> {output}")
    else:
        print(payload)
    return 0


def apply(path: Path) -> int:
    meanings: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    empty = [word for word, meaning in meanings.items() if not meaning.strip()]
    if empty:
        print(f"error: 意味が空の単語: {empty}", file=sys.stderr)
        return 1

    updated, skipped = 0, []
    with get_sessionmaker()() as session:
        for word, meaning in meanings.items():
            result = session.execute(
                update(VocabularyNotebook)
                .where(VocabularyNotebook.word == word, VocabularyNotebook.meaning.is_(None))
                .values(meaning=meaning.strip())
            )
            if result.rowcount:
                updated += 1
            else:
                skipped.append(word)
        session.commit()
    print(f"updated: {updated}, skipped (未登録 or 意味が設定済み): {len(skipped)} {skipped or ''}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_pending = sub.add_parser("pending")
    p_pending.add_argument("--output", type=Path)
    p_apply = sub.add_parser("apply")
    p_apply.add_argument("path", type=Path)
    args = parser.parse_args()
    return pending(args.output) if args.command == "pending" else apply(args.path)


if __name__ == "__main__":
    sys.exit(main())
