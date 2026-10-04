# リポジトリ直下のコマンド集。リポジトリルートから実行する想定（`make <target>`）。

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV      := $(REPO_ROOT)/.venv
PYTHON    := $(VENV)/bin/python
ALEMBIC   := $(VENV)/bin/alembic
REQUIREMENTS := $(REPO_ROOT)/requirements/requirements.txt

# lint/format で使うruffのバージョン。人間・Claude Code・Codexいずれが実行しても
# 同じ結果になるよう固定する（設定自体はリポジトリ直下のpyproject.tomlを参照）。
RUFF_VERSION := 0.16.6
RUFF := uvx ruff@$(RUFF_VERSION)

# 各ターゲットの引数（呼び出し時に指定する）。
#   DIR:  記事の作業ディレクトリ（例: intermediate/hidden-life-of-trees）
#   JSON: 翻訳JSON・意味JSONのパス
#   ARGS: スクリプトへの追加引数（例: ARGS=--dry-run）
#   MSG:  生成するAlembicマイグレーションの説明文
DIR  ?=
JSON ?=
ARGS ?=
MSG  ?=
MEANINGS_DIR := intermediate/meanings

.PHONY: help venv list-titles split apply-translations load-db vocab-pending vocab-apply \
	db-upgrade db-revision db-sql lint format format-check

help:
	@echo "make venv                       # .venv を作成し requirements/requirements.txt をインストール"
	@echo "make list-titles                # 登録済み記事のタイトル一覧（重複確認用）"
	@echo "make split DIR=intermediate/<slug>        # text.md を文分割し sentences.csv を出力"
	@echo "make apply-translations DIR=... JSON=...  # 翻訳JSONを sentences.csv へ反映"
	@echo "make load-db DIR=intermediate/<slug>      # 記事をDBへ登録（ARGS=--dry-run で検証のみ）"
	@echo "make vocab-pending                        # 意味が未設定の単語を $(MEANINGS_DIR)/pending.json へ出力"
	@echo "make vocab-apply JSON=...                 # 意味JSONを単語帳へ反映"
	@echo "make db-upgrade                 # Alembicマイグレーションを最新まで適用（venv自動構築）"
	@echo "make db-revision MSG=\"変更内容\"  # src/models の変更からマイグレーションを生成"
	@echo "make db-sql                     # 適用されるSQLを表示のみ（DBへは接続しない）"
	@echo "make lint                       # ruffでリポジトリ全体をチェック"
	@echo "make format                     # ruffでリポジトリ全体を自動整形"
	@echo "make format-check               # 整形が必要な差分が無いか確認（CI/pre-commit用）"

## .venv が無ければ作成し、requirements/requirements.txt の依存関係をインストールする
venv:
	@if [ ! -d "$(VENV)" ]; then \
		uv venv "$(VENV)" --python 3.14; \
	fi
	@uv pip install --quiet --python "$(PYTHON)" -r "$(REQUIREMENTS)"

define require
	@if [ -z "$($(1))" ]; then echo "$(1)=... を指定してください（make help 参照）" >&2; exit 1; fi
endef

list-titles: venv
	"$(PYTHON)" src/list_titles.py

split: venv
	$(call require,DIR)
	"$(PYTHON)" src/split_sentences.py "$(DIR)"

apply-translations: venv
	$(call require,DIR)
	$(call require,JSON)
	"$(PYTHON)" src/apply_translations.py "$(DIR)" "$(JSON)"

load-db: venv
	$(call require,DIR)
	"$(PYTHON)" src/load_to_db.py "$(DIR)" $(ARGS)

vocab-pending: venv
	"$(PYTHON)" src/vocab_meanings.py pending --output "$(MEANINGS_DIR)/pending.json"

vocab-apply: venv
	$(call require,JSON)
	"$(PYTHON)" src/vocab_meanings.py apply "$(JSON)"

## Alembicマイグレーションを最新まで適用する。接続先は config/settings.local.toml の [db] connection_string。
db-upgrade: venv
	cd "$(REPO_ROOT)" && "$(ALEMBIC)" upgrade head

## src/models の変更からAlembicマイグレーションを生成する（DB接続が必要）。
## 生成されたファイル（src/migrations/versions/配下）は内容を確認してからコミットすること。
db-revision: venv
	@if [ -z "$(MSG)" ]; then echo 'MSG="変更内容の説明" を指定してください（例: make db-revision MSG="add xxx column"）' >&2; exit 1; fi
	cd "$(REPO_ROOT)" && "$(ALEMBIC)" revision --autogenerate -m "$(MSG)"

## db-upgrade で流れるSQLを表示する（オフラインモード。DBへは接続しない）
db-sql: venv
	cd "$(REPO_ROOT)" && "$(ALEMBIC)" upgrade head --sql

## ruffでリポジトリ全体をチェックする（設定はpyproject.toml）。uvxがruffを自動取得するため事前インストール不要。
lint:
	$(RUFF) check .

## ruffでリポジトリ全体を自動整形する（フォーマット + 安全な自動修正）。
format:
	$(RUFF) format .
	$(RUFF) check --fix .

## 整形が必要な差分が無いかだけを確認する（ファイルは書き換えない）。pre-commitフックやCIから使う想定。
format-check:
	$(RUFF) format --check .
	$(RUFF) check .
