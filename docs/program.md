# Program（`src/`）

`src/`配下のPythonコードの役割・入出力。パイプライン上の位置づけは[workflow.md](workflow.md)、DBスキーマの詳細は
[db-guide.md](db-guide.md)を参照。

## モジュール間の依存関係

```
settings ──> db ──> list_titles / load_to_db / vocab_meanings
settings ──────────> split_sentences / list_titles / migrations/env.py
models   ──────────> list_titles / load_to_db / vocab_meanings / migrations/env.py
article  ──────────> split_sentences / apply_translations / load_to_db
```

- `settings`: 設定読み込みの起点。DB接続URLもここから
- `db`: `settings`の接続URLでエンジン・セッションを生成
- `article`: CSV/`text.md`の共通処理。DBには依存しない

## 実行方法

- 各スクリプトは`make`ターゲット経由で実行（`.venv`が無ければPython 3.14で作成し、`requirements/requirements.txt`をインストール）
- 直接実行する場合: `.venv/bin/python src/<script>.py ...`（リポジトリルートから）
- `src/`がimportパス（`from settings import ...`の形式）。スクリプト実行時は`src/`がスクリプトのディレクトリとしてパスに入り、
  Alembicは`alembic.ini`の`prepend_sys_path = %(here)s/src`で追加
- コーディング規約（ruff、`make format`/`make lint`）は[CLAUDE.md](../CLAUDE.md)を参照

## 共通モジュール

### `src/settings.py`

- `load_settings()`: `config/settings.toml`→`config/settings.local.toml`の順に読み、セクション単位で上書きマージした`dict`を返す（存在しないファイルはスキップ）
- `database_url()`: `[db] connection_string`を返す。`postgres://`・`postgresql://`は`postgresql+psycopg://`（psycopg3ドライバ）に置換。未設定なら`RuntimeError`

### `src/db.py`

- `get_engine()`: `database_url()`で`create_engine`（`pool_pre_ping=True`）
- `get_sessionmaker()`: 上記エンジンに束縛した`sessionmaker`

### `src/article.py`

`intermediate/<slug>/`の`text.md`・`sentences.csv`の読み書きと語数カウント。

- `read_article(dir)`: `text.md`を読み`Article`（`title`・`level`・`genre`・`paragraphs`）を返す。frontmatterの欠落・終端なし、`title`/`genre`の欠落、`level`がCEFR（`A1`〜`C2`）以外、本文なしは`ValueError`。本文は1行=1段落、空行は無視
- `Article.english_text`: 段落を改行で連結した全文（DBの`english_text`）
- `count_words(text)`: 英数字の連続を1語とし、アポストロフィ・ハイフンでつながる語も1語として数える
- `read_sentences(dir)` / `write_sentences(dir, rows)`: `sentences.csv`（列: `order_no`, `paragraph_no`, `english`, `japanese`）の読み書き。読み込み時に`order_no`・`paragraph_no`を`int`化

## スクリプト

### `src/split_sentences.py`

- make: `make split DIR=intermediate/<slug>`
- 入力: `text.md`／出力: `sentences.csv`（`japanese`は空）
- 処理:
  - 段落ごとにpysbd（`language="en"`, `clean=False`）で文分割
  - `split_quoted()`: 引用符（直線`"`・曲線`“”`）内に複数文があれば、引用符の中身を再分割し2文目以降の開始位置で元の文を切る（pysbdは引用符内の句読点を文末とみなさないため）。引用符は前後の断片に残る
- 検証（いずれも非0終了）:
  - 段落ごとに、分割結果の空白区切りの語列が原文と一致すること（`sentences.csv`は書き出してから後続チェック）
  - `genre`が`[generation] genres`に含まれること
  - 語数が`word_count_lower`〜`word_count_upper`の範囲内であること
- 標準出力: `title`・`level`・`genre`・段落数・文数・`word_count`（設定範囲）・出力パス

### `src/apply_translations.py`

- make: `make apply-translations DIR=... JSON=...`
- 入力: `sentences.csv`、翻訳JSON（`{"<order_no>": "<和訳>", ...}`）／出力: `sentences.csv`の`japanese`列を更新
- 検証: JSONに`sentences.csv`に無い`order_no`があれば非0終了（書き込まない）
- 和訳は前後の空白を除去して反映。出力の`untranslated`に`japanese`が空のままの`order_no`を表示

### `src/load_to_db.py`

- make: `make load-db DIR=intermediate/<slug> [ARGS=--dry-run]`
- 入力: `text.md`、`sentences.csv`／出力: `english_texts`・`sentences`への登録
- 検証（`validate()`、`--dry-run`でもDB非接続で実行）:
  - `order_no`が1始まりの連番
  - `paragraph_no`の集合が`text.md`の段落数と一致
  - 段落ごとに`english`の連結が`text.md`の該当段落と一致（空白区切りの語列で比較）
  - `english`・`japanese`に空欄なし
- 登録:
  - 同タイトル（`is_deleted = false`）の記事があれば拒否（非0終了）
  - `word_count`は`count_words(english_text)`で算出
  - `EnglishText`に`Sentence`を紐付けて1トランザクションでcommit。`IntegrityError`（部分ユニークインデックスによるタイトル重複等）はrollbackして非0終了
  - 成功時に`english_texts.id`と最後の`sentences.id`を表示
- `--dry-run`: 検証のみでDBに接続しない

### `src/list_titles.py`

- make: `make list-titles`
- 出力（標準出力）:
  - `## titles`: 未削除記事の`[level] [genre] title`（id順）と件数
  - `## articles per genre (少ない順)`: ジャンル別記事数。`[generation] genres`のうち0件のジャンルも含め、件数→ジャンル名の昇順
- 00-01・01-01の重複確認・ジャンル割り当てに使用

### `src/vocab_meanings.py`

サブコマンド2つ。

- `pending [--output <path>]`（make: `make vocab-pending`、出力先は`intermediate/meanings/pending.json`）: `meaning IS NULL`かつ未削除の単語をid順にJSON配列で出力。`--output`省略時は標準出力
- `apply <path>`（make: `make vocab-apply JSON=...`）: `{"<word>": "<意味>", ...}`を`meaning IS NULL`の単語にのみ反映（既存の意味は上書きしない）。意味が空の単語があれば非0終了（反映しない）。更新件数と、skipped（未登録または設定済み）の単語を表示

## DBスキーマ・マイグレーション

### `src/models/tables.py`・`src/models/__init__.py`

- `tables.py`: SQLAlchemy（Declarative）のモデル定義。`Base`、`EnglishText`（`english_texts`）、`Sentence`（`sentences`）、`VocabularyNotebook`（`vocabulary_notebook`）、`StudySession`（`study_sessions`）、`Bookmark`（`bookmarks`）
  - 全テーブル共通の`is_deleted`は`is_deleted_column()`で定義
  - `english_texts.title`に部分ユニークインデックス`uq_english_texts_title_active`（`NOT is_deleted`）
  - `EnglishText.sentences`は`order_no`順のrelationship
- `__init__.py`: 上記クラスを再エクスポート（`from models import EnglishText`の形式で使う）
- 変更後は`make db-revision MSG="..."`でマイグレーションを生成（手順は[CLAUDE.md](../CLAUDE.md)の「DB」）

### `src/migrations/`

Alembic（`make db-upgrade`・`make db-revision`・`make db-sql`から実行）。

- `env.py`: 接続URLを`settings.database_url()`から取得（`alembic.ini`には書かない）。`target_metadata`は`models.Base.metadata`。オンライン（`NullPool`で接続）とオフライン（`make db-sql`、SQL出力のみ）の両モードに対応
- `versions/`: マイグレーションファイル（ファイル名は`alembic.ini`の`file_template`で`<年月日>_<rev>_<slug>`）
  - `20261004_0001_initial_schema.py`（rev `0001`）: 初期スキーマ4テーブル（english_texts, sentences, vocabulary_notebook, study_sessions）、タイトルの部分ユニークインデックス、`set_updated_at()`関数と`vocabulary_notebook`の`updated_at`トリガー
  - `20261004_199311d7228a_add_genre_to_english_texts.py`: `english_texts.genre`の追加
  - `20261004_6d42bd019f49_add_bookmarks.py`: `bookmarks`テーブルと、その`updated_at`トリガー
