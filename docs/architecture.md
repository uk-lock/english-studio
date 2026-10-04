# アーキテクチャ

English Studio全体の設計と、その理由。セットアップ・使い方は[README.md](../README.md)、パイプラインの手順は
[workflow.md](workflow.md)、DBの詳細は[db-guide.md](db-guide.md)を参照。

## 責務分離

ローカルバッチとGPT Siteを完全に分離。共有点はNeon(PostgreSQL)のみ。

| 担当 | 役割 | LLM |
|---|---|---|
| ローカルバッチ（本リポジトリ） | 記事の生成・文分割・翻訳・DB登録、単語の意味補完 | 使う（Claude Code/Codex） |
| GPT Site（本リポジトリの範囲外） | UI（記事一覧・読書画面・単語帳・学習時間・しおり）。DBの読み書きのみ | 呼ばない |

```
┌─────────────── ローカル（本リポジトリ）───────────────┐
│ Claude Code / Codex                                   │
│   Skill（.claude/skills, .agents/skills）             │
│   subagent（.claude/agents, .codex/agents）           │
│        │ 呼び出し            ▲ 読み書き               │
│        ▼                     │                        │
│   Program（src/、make経由） ─┴─ intermediate/         │
└────────┬──────────────────────────────────────────────┘
         │ 書き込み（記事・文の登録、meaningの補完）
         ▼
   Neon (PostgreSQL)
         ▲
         │ 読み書き（記事閲覧、単語帳追加、学習時間・しおり）
   GPT Site（UI）
```

採用理由:

- GPT Siteをシンプルに保つ（DB操作とUIのみ）
- AI処理（モデル・プロンプト・バッチ）をアプリに影響なく改善できる
- 読書中にLLMの応答を待たない
- MVPを小さく保つ

## SkillとProgramの分離

| 種別 | 対象工程 | 配置 | 実行 |
|---|---|---|---|
| Skill | LLMの判断が必要な工程（記事生成・翻訳・意味生成・誤分割の確認等） | `.claude/skills/`（Claude Code向け）と`.agents/skills/`（Codex向け）に同一内容 | Claude Code/Codex |
| Program | 決定論的な工程（文分割・検証・DB登録等） | `src/` | `Makefile`経由（`.venv`、Python 3.14） |

subagent（`article-writer`等）は`.claude/agents/*.md`と`.codex/agents/*.toml`に同一subagentの2ランタイム表現として定義。
運用ルールは[CLAUDE.md](../CLAUDE.md)を参照。

## 主要な設計判断

| 判断 | 理由 |
|---|---|
| 単一ユーザー前提（ユーザーテーブルなし） | 利用者は自分1人のため |
| 全テーブル論理削除（`is_deleted`）、物理削除しない | 単語帳の`sentence_ids`等からの参照を壊さないため。読み出しは常に`is_deleted = false`で絞る |
| 登録済みの記事・文は更新しない | `vocabulary_notebook.sentence_ids`が`sentences.id`を参照しており、再登録でIDが変わると参照が壊れるため |
| 同タイトル（未削除）の記事は登録拒否 | 上記により上書きができないため。`title`に`NOT is_deleted`条件の部分ユニークインデックス |
| 単語の意味は登録時に埋めず、後からバッチで補完（`meaning IS NULL`が対象） | GPT SiteからLLMを呼ばないため |
| `word`は小文字・見出し語化なし・ユニーク（削除済み含む） | `running`と`run`は別単語扱い。削除済みの再追加は新規行を作らず`is_deleted`を戻す（upsert） |
| 学習時間は読書1回=1行（`study_sessions`） | 日別集計を可能にするため。記事ごとの累計1行方式では日別が復元できない |
| しおりは1記事0〜1件（`bookmarks.text_id`ユニーク、upsert） | どの段落まで読んだかを記事ごとに1箇所保持。設定・移動・再設定をすべて同じupsertで扱え、行が増えない |
| `updated_at`はDBトリガーで維持 | GPT Siteからも更新されるため（ORM側の自動更新に頼れない） |
| 段落は`sentences.paragraph_no`で保持（`english_text`は改行=段落） | 段落単位の表示・しおりのため |
| 記事の一括生成は記事ごとにsubagentを分ける | 記事間の文脈の混入防止 |
| テーマ・タイトル・ジャンルの割り当てはメインが全体を見て決め、subagentは並列実行 | 重複判断には全体像が必要。割り当て後は記事ごとに独立（`intermediate/<slug>/`が別、DB登録は記事単位のトランザクション） |
| ジャンルを`english_texts.genre`に記録し、記事数の少ないジャンルから割り当て | ジャンルの偏り防止 |
| 文分割はpysbd。引用符内の複数文はProgram側で追加分割 | pysbdは引用符内の句読点を文末とみなさず、引用符内の複数文を1文にまとめるため |

## データモデル概要

```
english_texts 1 ──< * sentences
english_texts 1 ──< * study_sessions
english_texts 1 ──  0..1 bookmarks
vocabulary_notebook.sentence_ids (JSONB配列) ──> sentences.id
```

テーブル定義・書き込み担当・よく使うSQLは[db-guide.md](db-guide.md)、モデル定義は`src/models/tables.py`を参照。

## 将来の拡張候補（MVP対象外）

- 単語の品詞・CEFR・例文・類義語の生成
- 復習アルゴリズム
- 苦手単語ランキング
- 学習統計ダッシュボード
- リスニング・英作文等
