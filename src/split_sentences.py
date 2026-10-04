"""text.md を文単位に分割し sentences.csv を出力する。語数が設定範囲外なら非0で終了する。

使い方: python src/split_sentences.py intermediate/<slug>
"""

import argparse
import re
import sys
from pathlib import Path

import pysbd

from article import SENTENCES_FILE, count_words, read_article, write_sentences
from settings import load_settings

# 引用符で囲まれた範囲（直線引用符・曲線引用符）
QUOTE_PATTERN = re.compile(r'"[^"]+"|“[^”]+”')


def split_quoted(sentence: str, segmenter: pysbd.Segmenter) -> list[str]:
    """引用符内に複数の文があれば、その文境界でも分割する。

    pysbd は `"Why now?" he asked.` を誤分割しないよう引用符内の句読点を文末とみなさないため、
    `"A. B."` のように引用符内に複数文があると1文にまとめてしまう。引用符の中身だけを
    改めて分割し、2文目以降の開始位置で元の文を切る（引用符は前後の断片に残る）。
    """
    cut_points = []
    for quote in QUOTE_PATTERN.finditer(sentence):
        inner_start = quote.start() + 1
        spans = segmenter.segment(sentence[inner_start : quote.end() - 1])
        cut_points.extend(inner_start + span.start for span in spans[1:])

    pieces, prev = [], 0
    for point in cut_points:
        pieces.append(sentence[prev:point])
        prev = point
    pieces.append(sentence[prev:])
    return [piece.strip() for piece in pieces if piece.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article_dir", type=Path)
    args = parser.parse_args()

    article = read_article(args.article_dir)
    segmenter = pysbd.Segmenter(language="en", clean=False)
    span_segmenter = pysbd.Segmenter(language="en", clean=False, char_span=True)

    rows = []
    for paragraph_no, paragraph in enumerate(article.paragraphs, start=1):
        sentences = [
            piece for s in segmenter.segment(paragraph) for piece in split_quoted(s, span_segmenter)
        ]
        if " ".join(sentences).split() != paragraph.split():
            print(f"error: 段落{paragraph_no}の分割結果が原文と一致しません", file=sys.stderr)
            return 1
        for sentence in sentences:
            rows.append(
                {
                    "order_no": len(rows) + 1,
                    "paragraph_no": paragraph_no,
                    "english": sentence,
                    "japanese": "",
                }
            )
    write_sentences(args.article_dir, rows)

    generation = load_settings().get("generation", {})
    lower, upper = generation.get("word_count_lower"), generation.get("word_count_upper")
    word_count = count_words(article.english_text)
    print(f"title: {article.title}")
    print(f"level: {article.level}")
    print(f"genre: {article.genre}")
    print(f"paragraphs: {len(article.paragraphs)}, sentences: {len(rows)}")
    print(f"word_count: {word_count} (設定範囲: {lower}〜{upper})")
    print(f"output: {args.article_dir / SENTENCES_FILE}")

    genres = generation.get("genres")
    if genres and article.genre not in genres:
        print(
            f"error: genre {article.genre!r} が [generation] genres にありません", file=sys.stderr
        )
        return 1
    if lower is not None and word_count < lower or upper is not None and word_count > upper:
        print("error: 語数が config/settings.toml の [generation] の範囲外です", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
