"""記事ファイル（intermediate/<slug>/text.md）・文CSVの読み書きと語数カウント。

text.md の形式:
    ---
    title: <タイトル>
    level: <CEFRレベル>
    genre: <ジャンル>
    ---
    <段落1>
    <段落2>

本文は1行=1段落（改行で段落を区切る）。空行は無視する。
"""

import csv
import re
from dataclasses import dataclass
from pathlib import Path

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
CSV_COLUMNS = ("order_no", "paragraph_no", "english", "japanese")
TEXT_FILE = "text.md"
SENTENCES_FILE = "sentences.csv"

# 英単語（数字・アポストロフィ・ハイフンを含む語は1語として数える）
WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*")


@dataclass
class Article:
    title: str
    level: str
    genre: str
    paragraphs: list[str]

    @property
    def english_text(self) -> str:
        return "\n".join(self.paragraphs)


def count_words(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def read_article(article_dir: Path) -> Article:
    path = article_dir / TEXT_FILE
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: 先頭にfrontmatter（---）がありません")
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as e:
        raise ValueError(f"{path}: frontmatterの終端（---）がありません") from e

    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    title, level, genre = meta.get("title", ""), meta.get("level", ""), meta.get("genre", "")
    if not title:
        raise ValueError(f"{path}: frontmatterに title がありません")
    if not genre:
        raise ValueError(f"{path}: frontmatterに genre がありません")
    if level not in CEFR_LEVELS:
        raise ValueError(f"{path}: level は {'/'.join(CEFR_LEVELS)} のいずれか（現在: {level!r}）")

    paragraphs = [line.strip() for line in lines[end + 1 :] if line.strip()]
    if not paragraphs:
        raise ValueError(f"{path}: 本文がありません")
    return Article(title=title, level=level, genre=genre, paragraphs=paragraphs)


def read_sentences(article_dir: Path) -> list[dict]:
    with (article_dir / SENTENCES_FILE).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["order_no"] = int(row["order_no"])
        row["paragraph_no"] = int(row["paragraph_no"])
    return rows


def write_sentences(article_dir: Path, rows: list[dict]) -> None:
    with (article_dir / SENTENCES_FILE).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows({k: row[k] for k in CSV_COLUMNS} for row in rows)
