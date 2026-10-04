"""翻訳JSON（{"<order_no>": "<和訳>", ...}）を sentences.csv の japanese 列へ書き戻す。

使い方: python src/apply_translations.py intermediate/<slug> <翻訳JSONのパス>
"""

import argparse
import json
import sys
from pathlib import Path

from article import read_sentences, write_sentences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article_dir", type=Path)
    parser.add_argument("translations", type=Path)
    args = parser.parse_args()

    translations = json.loads(args.translations.read_text(encoding="utf-8"))
    rows = read_sentences(args.article_dir)
    by_order = {row["order_no"]: row for row in rows}

    unknown = [key for key in translations if int(key) not in by_order]
    if unknown:
        print(f"error: sentences.csv に存在しない order_no: {unknown}", file=sys.stderr)
        return 1
    for key, japanese in translations.items():
        by_order[int(key)]["japanese"] = japanese.strip()
    write_sentences(args.article_dir, rows)

    missing = [row["order_no"] for row in rows if not row["japanese"]]
    print(f"applied: {len(translations)}, untranslated: {len(missing)} {missing or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
