"""DBスキーマ定義。変更後は `make db-revision MSG="..."` でマイグレーションを生成する。

書き込み担当:
- english_texts: ローカルバッチ（登録時）、GPT Site（read_at・is_deleted の更新のみ）
- sentences: ローカルバッチ（登録時）
- vocabulary_notebook: GPT Site（単語追加）、ローカルバッチ（meaning の補完のみ）
- study_sessions / bookmarks: GPT Site
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def is_deleted_column() -> Mapped[bool]:
    """論理削除フラグ。全テーブル共通で、物理削除は行わない。"""
    return mapped_column(Boolean, nullable=False, server_default=text("false"))


class EnglishText(Base):
    """英文マスタ（記事単位）。english_text は改行で段落を区切る。

    title は論理削除されていない記事の中で一意（同じタイトルの記事は登録を拒否する）。
    登録後に更新してよいのは read_at・is_deleted のみ（GPT Site が更新する）。
    """

    __tablename__ = "english_texts"
    __table_args__ = (
        Index(
            "uq_english_texts_title_active",
            "title",
            unique=True,
            postgresql_where=text("NOT is_deleted"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(Text, nullable=False)  # CEFRレベル（B1/B2/C1など）
    genre: Mapped[str] = mapped_column(Text, nullable=False)  # settings.toml の genres の値
    english_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # 読了日時。NULLは未読
    is_deleted: Mapped[bool] = is_deleted_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sentences: Mapped[list[Sentence]] = relationship(
        back_populates="english_text", order_by="Sentence.order_no", passive_deletes=True
    )


class Sentence(Base):
    """文章マスタ（英文を文単位に分割し和訳と紐付ける）。"""

    __tablename__ = "sentences"
    __table_args__ = (UniqueConstraint("text_id", "order_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_id: Mapped[int] = mapped_column(
        ForeignKey("english_texts.id", ondelete="CASCADE"), nullable=False
    )
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 記事内の通し番号（1始まり）
    paragraph_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 段落番号（1始まり）
    english: Mapped[str] = mapped_column(Text, nullable=False)
    japanese: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = is_deleted_column()

    english_text: Mapped[EnglishText] = relationship(back_populates="sentences")


class VocabularyNotebook(Base):
    """単語帳。word は小文字で保存し、見出し語化はしない（running と run は別単語）。

    meaning が NULL のレコードは、ローカルの定期バッチがLLMで辞書的な意味を生成して埋める。
    word はユニーク（論理削除済みも含む）のため、削除済みの単語を再追加する場合は is_deleted を false に戻す。
    lookup_count は「単語帳へ追加」が押された回数。
    """

    __tablename__ = "vocabulary_notebook"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    meaning: Mapped[str | None] = mapped_column(Text)
    sentence_ids: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    lookup_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_deleted: Mapped[bool] = is_deleted_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StudySession(Base):
    """学習時間（読書1回=1行）。記事別・日別の集計は GROUP BY で行う。"""

    __tablename__ = "study_sessions"
    __table_args__ = (CheckConstraint("reading_seconds >= 0"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_id: Mapped[int] = mapped_column(
        ForeignKey("english_texts.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reading_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_deleted: Mapped[bool] = is_deleted_column()


class Bookmark(Base):
    """しおり（どの段落まで読んだか）。1記事につき0〜1件。

    text_id がユニークのため、GPT Site は INSERT ... ON CONFLICT (text_id) DO UPDATE で
    paragraph_no を更新する（行は追加しない）。しおりを外すときは is_deleted を true にし、
    再度挟むときは同じ upsert で is_deleted を false に戻す。
    """

    __tablename__ = "bookmarks"
    __table_args__ = (CheckConstraint("paragraph_no >= 1"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_id: Mapped[int] = mapped_column(
        ForeignKey("english_texts.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    paragraph_no: Mapped[int] = mapped_column(Integer, nullable=False)  # sentences.paragraph_no
    is_deleted: Mapped[bool] = is_deleted_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
