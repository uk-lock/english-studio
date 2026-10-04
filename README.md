# English Studio

英語多読アプリ。本リポジトリはローカルバッチ（Claude Code/CodexのSkillによる英文生成・翻訳・単語の意味補完と、
Neon(PostgreSQL)への登録）を担当。UIはGPT Site（ホスティングサービス）側のアプリがDBを読み書きして提供し、
本リポジトリの範囲外。アプリからLLMは呼ばない。

## 全体構成

```
ローカルバッチ（本リポジトリ）  ──書き込み──▶  Neon (PostgreSQL)  ◀──読み書き──  GPT Site（UI）
  記事・文の登録、単語の意味補完                                                 記事閲覧、単語帳追加、学習時間・しおり
```

## セットアップ

1. uvをインストールする（`brew install uv`等）。Python 3.14と依存（`requirements/requirements.txt`）は各makeターゲットが
   `.venv`に自動構築する。
2. `config/settings.local.toml`を作成し、Neonの接続文字列を書く（Git管理外）。
   ```toml
   [db]
   connection_string = "postgresql://<user>:<password>@<host>/<database>"
   ```
3. `make db-upgrade`でスキーマを作成する。
4. gitleaksをインストールし（`brew install gitleaks`）、`git config core.hooksPath .githooks`を実行する
   （pre-commitで`gitleaks`による秘密情報スキャンと、`.py`変更時の`make format-check`を実行）。

## 使い方

### 記事の一括生成

Claude Codeで`00-01-generate-articles`を実行（「記事を作って」等）。

- 本数・レベル・語数範囲・ジャンル候補: `config/settings.toml`の`[generation]`（`level`・`word_count_lower`・
  `word_count_upper`・`article_count`・`genres`）
- ジャンル: 登録済み記事の少ないものから割り当て
- 処理: 記事ごとにsubagent `article-writer`が`01-01`（生成）→ `02-01`（文分割）→ `03-01`（翻訳）→ `04-01`（DB登録）
  を並列実行
- 中間ファイル: `intermediate/<slug>/`（`text.md`・`sentences.csv`・`translations.json`。Git管理外）

### 単語の意味補完

`10-01-fill-meanings`を実行（「意味を埋めて」等）。`meaning`がNULLの単語に辞書的な日本語の意味を付与。

## makeコマンド一覧

| コマンド | 説明 |
|---|---|
| `make list-titles` | 登録済み記事のタイトル一覧（重複確認用） |
| `make split DIR=intermediate/<slug>` | `text.md`を文分割し`sentences.csv`を出力 |
| `make apply-translations DIR=... JSON=...` | 翻訳JSONを`sentences.csv`へ反映 |
| `make load-db DIR=intermediate/<slug> [ARGS=--dry-run]` | 記事をDBへ登録（`ARGS=--dry-run`で検証のみ） |
| `make vocab-pending` | 意味が未設定の単語を`intermediate/meanings/pending.json`へ出力 |
| `make vocab-apply JSON=...` | 意味JSONを単語帳へ反映 |
| `make db-upgrade` | Alembicマイグレーションを最新まで適用 |
| `make db-revision MSG="..."` | `src/models`の変更からマイグレーションを生成 |
| `make db-sql` | 適用されるSQLを表示のみ |
| `make lint` | ruffでチェック |
| `make format` | ruffで自動整形 |
| `make format-check` | 整形差分の確認 |

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `src/` | Program（`models/`: DBスキーマ、`migrations/`: Alembic） |
| `config/` | 設定ファイル（`settings.toml`: 共有、`settings.local.toml`: 秘密情報・Git管理外） |
| `requirements/` | 依存定義 |
| `intermediate/` | 中間ファイル（Git管理外） |
| `.claude/`・`.agents/` | Skill（Claude Code向け・Codex向けに同一内容） |
| `.claude/agents/`・`.codex/agents/` | subagent定義 |
| `docs/` | ドキュメント |

## 関連ドキュメント

- システム全体の設計と理由: [docs/architecture.md](docs/architecture.md)
- パイプラインの全体フローと各ステップの入出力: [docs/workflow.md](docs/workflow.md)
- `src/`配下のPythonコードの説明: [docs/program.md](docs/program.md)
- DBの詳細（テーブル定義・GPT Site側の読み書き方法）: [docs/db-guide.md](docs/db-guide.md)
- エージェント向け運用ルール: [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md)
