# DBガイド（GPT Site向け）

GPT Site側でアプリ（UI）を作る人・その作成を手伝うAI向け。本リポジトリのコードを読まずに、DBだけを見て正しく読み書きするための資料。

## 前提

- DB: Neon（PostgreSQL）
- 利用者は1人（ユーザーテーブルなし）
- 記事（`english_texts`）と文（`sentences`）はローカルバッチが登録。GPT Siteは読み出しに加え、`english_texts`の`read_at`（読了）・`is_deleted`（記事削除）の更新のみ可
- アプリからLLMは呼ばない。単語の意味（`vocabulary_notebook.meaning`）は後からバッチが埋める

## 共通ルール

- 全テーブルに`is_deleted BOOLEAN NOT NULL DEFAULT false`
- 削除は論理削除（`is_deleted = true`）。物理削除（`DELETE`）はしない
- 読み出し時は常に`is_deleted = false`で絞る。記事が削除済みなら、その記事の文も対象外
- 日時の型は`timestamptz`

## テーブル一覧

| テーブル | 用途 | 書き込み担当 |
|---|---|---|
| `english_texts` | 記事 | バッチ（登録）、GPT Site（`read_at`・`is_deleted`のみ） |
| `sentences` | 文（英文と和訳） | バッチ |
| `vocabulary_notebook` | 単語帳 | GPT Site（追加）、バッチ（`meaning`の補完のみ） |
| `study_sessions` | 学習時間 | GPT Site |
| `bookmarks` | しおり | GPT Site |

### english_texts（記事）

書き込み: バッチが登録、GPT Siteが`read_at`（読了管理）・`is_deleted`（記事の論理削除）のみ更新。その他のカラムは登録後に更新しない。

| カラム | 型 | 説明 |
|---|---|---|
| `id` | `SERIAL` PK | |
| `title` | `TEXT NOT NULL` | タイトル。未削除の記事の中で一意 |
| `level` | `TEXT NOT NULL` | CEFRレベル（`A1`〜`C2`） |
| `genre` | `TEXT NOT NULL` | ジャンル |
| `english_text` | `TEXT NOT NULL` | 英文全文。改行が段落区切り |
| `word_count` | `INTEGER NOT NULL` | 語数 |
| `read_at` | `timestamptz NULL` | 読了日時。NULLは未読。GPT Siteが更新 |
| `is_deleted` | `BOOLEAN NOT NULL DEFAULT false` | 論理削除フラグ |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | 登録日時 |

### sentences（文）

書き込み: バッチ。

| カラム | 型 | 説明 |
|---|---|---|
| `id` | `SERIAL` PK | 単語帳の`sentence_ids`から参照される |
| `text_id` | `INTEGER NOT NULL` → `english_texts.id` | 所属する記事 |
| `order_no` | `INTEGER NOT NULL` | 記事内の通し番号（1始まり）。`(text_id, order_no)`で一意 |
| `paragraph_no` | `INTEGER NOT NULL` | 段落番号（1始まり） |
| `english` | `TEXT NOT NULL` | 英文 |
| `japanese` | `TEXT NOT NULL` | 和訳 |
| `is_deleted` | `BOOLEAN NOT NULL DEFAULT false` | 論理削除フラグ |

表示上の注意:

- `order_no`順に並べ、`paragraph_no`が変わるところで段落を区切る
- 引用符内の会話文は文ごとに分かれるため、引用符の開始と終了が別の文に入ることがある

### vocabulary_notebook（単語帳）

書き込み: GPT Siteが単語を追加、バッチが`meaning`を補完。

| カラム | 型 | 説明 |
|---|---|---|
| `id` | `SERIAL` PK | |
| `word` | `TEXT NOT NULL UNIQUE` | 単語。小文字で保存。削除済みも含めて一意。見出し語化しない（`running`と`run`は別単語） |
| `meaning` | `TEXT NULL` | 辞書的な日本語の意味（「；」区切り）。NULLはバッチ未処理 |
| `sentence_ids` | `JSONB NOT NULL DEFAULT '[]'` | その単語を登録した文の`sentences.id`の配列 |
| `lookup_count` | `INTEGER NOT NULL DEFAULT 1` | 「単語帳へ追加」を押した回数 |
| `is_deleted` | `BOOLEAN NOT NULL DEFAULT false` | 論理削除フラグ |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | 登録日時 |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | 更新日時。UPDATE時にDBトリガーで自動更新（アプリ側で設定不要） |

`word`は削除済みも含めて一意のため、削除済みの単語を再追加するときは新規行を作らず`is_deleted`を`false`に戻す（下記「単語帳へ追加」のSQLで対応済み）。

### study_sessions（学習時間）

書き込み: GPT Site。読書1回=1行で、INSERTのみ。記事別・日別の集計は`GROUP BY`で行う。

| カラム | 型 | 説明 |
|---|---|---|
| `id` | `SERIAL` PK | |
| `text_id` | `INTEGER NOT NULL` → `english_texts.id` | 読んだ記事 |
| `started_at` | `timestamptz NOT NULL` | 読書開始日時 |
| `reading_seconds` | `INTEGER NOT NULL`（`>= 0`） | その回の読書秒数 |
| `is_deleted` | `BOOLEAN NOT NULL DEFAULT false` | 論理削除フラグ |

### bookmarks（しおり）

書き込み: GPT Site。1記事につき0〜1件。

| カラム | 型 | 説明 |
|---|---|---|
| `id` | `SERIAL` PK | |
| `text_id` | `INTEGER NOT NULL UNIQUE` → `english_texts.id` | 対象の記事 |
| `paragraph_no` | `INTEGER NOT NULL`（`>= 1`） | どの段落まで読んだか（`sentences.paragraph_no`に対応） |
| `is_deleted` | `BOOLEAN NOT NULL DEFAULT false` | 論理削除フラグ（しおりを外した状態） |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | 登録日時 |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | 更新日時。UPDATE時にDBトリガーで自動更新（アプリ側で設定不要） |

`text_id`が一意のため、しおりの設定・移動・再設定はすべてupsertで行う（行を追加しない）。

## よく使うSQL

パラメータは`$1`, `$2`, ...で表記。

### 記事一覧

```sql
SELECT id, title, level, genre, word_count, read_at
FROM english_texts
WHERE is_deleted = false
ORDER BY id;
```

### 読了にする・未読に戻す

`$1`: 記事ID。

```sql
-- 読了にする
UPDATE english_texts SET read_at = now() WHERE id = $1;
-- 未読に戻す
UPDATE english_texts SET read_at = NULL WHERE id = $1;
```

### 記事を削除する

`$1`: 記事ID。文・しおり・学習時間の行は触らない（読み出し時に記事側の`is_deleted`で除外される）。

```sql
UPDATE english_texts SET is_deleted = true WHERE id = $1;
```

### 記事の文を段落ごとに取得

`$1`: 記事ID。`paragraph_no`が変わるところで段落を区切って表示する。

```sql
SELECT id, order_no, paragraph_no, english, japanese
FROM sentences
WHERE text_id = $1 AND is_deleted = false
ORDER BY order_no;
```

### 単語帳へ追加（upsert）

`$1`: 単語（アプリ側で小文字化して渡す）、`$2`: クリックした文の`sentences.id`。

- 未登録: 新規行を作成
- 登録済み: `sentence_ids`に文IDを重複なく追加し、`lookup_count`を+1
- 削除済み: 上記に加えて`is_deleted = false`に戻して復活

```sql
INSERT INTO vocabulary_notebook (word, sentence_ids)
VALUES (lower($1), jsonb_build_array($2::int))
ON CONFLICT (word) DO UPDATE SET
  sentence_ids = CASE
    WHEN vocabulary_notebook.sentence_ids @> jsonb_build_array($2::int)
      THEN vocabulary_notebook.sentence_ids
    ELSE vocabulary_notebook.sentence_ids || jsonb_build_array($2::int)
  END,
  lookup_count = vocabulary_notebook.lookup_count + 1,
  is_deleted = false;
```

### 単語の例文表示

`$1`: `vocabulary_notebook.id`。`sentence_ids`に含まれる文と、その記事タイトルを取得する。

```sql
SELECT s.english, s.japanese, t.title
FROM sentences s
JOIN english_texts t ON t.id = s.text_id
WHERE s.id IN (
  SELECT jsonb_array_elements_text(sentence_ids)::int
  FROM vocabulary_notebook
  WHERE id = $1
)
  AND s.is_deleted = false
  AND t.is_deleted = false;
```

### 単語クリック時のポップアップ

- 意味: 単語帳にあれば`meaning`を表示。`meaning`がNULLなら「意味は準備中」等を表示
- 例文: クリックした文の`english`/`japanese`（「記事の文を段落ごとに取得」で取得済みの値）

```sql
-- $1: クリックした単語（アプリ側で小文字化して渡す）
SELECT meaning
FROM vocabulary_notebook
WHERE word = lower($1) AND is_deleted = false;
```

行が返らなければ単語帳に未登録。

### 学習時間の記録

`$1`: 記事ID、`$2`: 読書開始日時（timestamptz）、`$3`: 読書秒数（0以上）。

```sql
INSERT INTO study_sessions (text_id, started_at, reading_seconds)
VALUES ($1, $2, $3);
```

### 学習時間の集計

日別（日本時間で日付を区切る）:

```sql
SELECT date(started_at AT TIME ZONE 'Asia/Tokyo') AS day,
       sum(reading_seconds) AS total_seconds
FROM study_sessions
WHERE is_deleted = false
GROUP BY day
ORDER BY day;
```

記事別:

```sql
SELECT t.id, t.title, sum(ss.reading_seconds) AS total_seconds
FROM study_sessions ss
JOIN english_texts t ON t.id = ss.text_id
WHERE ss.is_deleted = false AND t.is_deleted = false
GROUP BY t.id, t.title
ORDER BY t.id;
```

### しおりの設定・移動（upsert）

`$1`: 記事ID、`$2`: 段落番号（1以上）。外したしおりを再設定する場合も同じSQL（`is_deleted = false`に戻る）。

```sql
INSERT INTO bookmarks (text_id, paragraph_no)
VALUES ($1, $2)
ON CONFLICT (text_id) DO UPDATE SET
  paragraph_no = EXCLUDED.paragraph_no,
  is_deleted = false;
```

### しおりを外す

```sql
UPDATE bookmarks SET is_deleted = true WHERE text_id = $1;
```

### しおりの取得

行が返らなければしおりなし。

```sql
SELECT paragraph_no FROM bookmarks WHERE text_id = $1 AND is_deleted = false;
```

## やってはいけないこと

- `english_texts`の`read_at`・`is_deleted`以外の更新、`sentences`の更新・削除: 単語帳の`sentence_ids`が文IDを参照しており、IDが変わると参照が壊れる
- 物理削除（`DELETE`）: 削除は必ず`is_deleted = true`で行う
- `vocabulary_notebook.meaning`の上書き: バッチが埋める

## スキーマ変更

スキーマ変更は本リポジトリ側（Alembic）で行う。GPT Site側から`CREATE`/`ALTER`等のDDLを実行しない。
