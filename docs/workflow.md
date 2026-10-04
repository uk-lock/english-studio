# ワークフロー

パイプラインの全体フローと各ステップの入出力。設計の理由は[architecture.md](architecture.md)、各ステップの詳細な手順は
`.claude/skills/<name>/SKILL.md`（Codex向けは`.agents/skills/`に同一内容）が正。

各Skillの完了条件を満たしたら、ユーザーに確認を挟まず次のステップへ進む（[CLAUDE.md](../CLAUDE.md)の「Skill完了後の進行判断」）。

## 設定値（`config/settings.toml`の`[generation]`）

| キー | 使う箇所 |
|---|---|
| `level` | 01-01（`text.md`の`level`にそのまま記載） |
| `word_count_lower`・`word_count_upper` | 01-01（中央付近を目標に執筆）、02-01（`make split`が範囲外なら非0終了） |
| `article_count` | 00-01（1回の生成本数。ユーザーが本数を明示した場合はそちらを優先） |
| `genres` | 00-01・01-01（割り当て候補。表記はそのまま使う）、02-01（`genres`に無い`genre`なら非0終了）、`make list-titles`（未使用ジャンルも0件として表示） |

## パイプラインA: 記事登録

```
00-01-generate-articles（メイン）
  │ make list-titles → 割り当て表（ジャンル・テーマ・タイトル・slug）
  │
  ├─ article-writer（記事1）─┐
  ├─ article-writer（記事2）─┼─ 並列
  └─ article-writer（記事N）─┘
       │
       ▼ 記事ごとに順に実行
     01-01-generate-text   → intermediate/<slug>/text.md
     02-01-split-sentences → intermediate/<slug>/sentences.csv   （語数範囲外・genre不正 → 01-01へ）
     03-01-translate       → translations.json → sentences.csvのjapanese列
     04-01-load-to-db      → english_texts / sentences           （タイトル重複 → 失敗報告 → 00-01が割り当て直し）
```

### 00-01-generate-articles（Skill、メインが実行）

- 実行: Claude Codeで「記事を作って」等
- 入力: `[generation]`、`make list-titles`の出力（登録済みタイトル・ジャンル別記事数）、`intermediate/`配下の既存slug
- 出力: 割り当て表と、記事ごとの`article-writer`起動
- 割り当て: ジャンルは記事数の少ないものから。タイトル・テーマは登録済み・同一バッチ内とも重複させない。slugは既存とも重複させない
- エラー時: タイトル重複なら割り当てを作り直して再起動、それ以外は同じ割り当てで再起動。再起動時は再実行である旨を伝える

### 01-01-generate-text（Skill）

- 入力: `[generation]`、00-01からの割り当て（ジャンル・テーマ・タイトル・slug、再実行か否か）
- 出力: `intermediate/<slug>/text.md`
- チェック: 割り当てありでも、登録済みタイトルとの同一は念のため確認（あれば失敗報告）
- 再実行時: 同じslugのディレクトリ（前回失敗の残り、DB未登録）があれば`text.md`を上書き。後続ファイルも作り直される
- 差し戻しを受けた場合: 語数範囲外→本文を加筆/削除、`genre`不正→`genres`の表記に修正

### 02-01-split-sentences（Skill。分割はProgram、誤分割の確認はLLM）

- 実行: `make split DIR=intermediate/<slug>`
- 入力: `text.md`
- 出力: `sentences.csv`（`japanese`は空）
- チェック: `make split`が語数範囲外・`genre`不正・分割結果の原文不一致で非0終了。略語（`Dr.`・`U.S.`等）の誤分割はSkillが目視確認し、行の結合で修正（`english`は半角スペース1つで連結、`order_no`は振り直し、`paragraph_no`は変えない）
- 差し戻し: 語数範囲外・`genre`不正 → 01-01

### 03-01-translate（Skill。翻訳はLLM、反映はProgram）

- 実行: 翻訳後に`make apply-translations DIR=intermediate/<slug> JSON=intermediate/<slug>/translations.json`
- 入力: `sentences.csv`
- 出力: `translations.json`、`sentences.csv`の`japanese`列
- チェック: 出力の`untranslated`が0であること。英文と訳文を通しで読み比べる自己チェック（訳抜け・原文にない説明・数字や固有名詞の誤り）
- 反映は必ず`make apply-translations`経由（CSVを直接編集しない）

### 04-01-load-to-db（Skill。検証・登録はProgram）

- 実行: `make load-db DIR=intermediate/<slug> ARGS=--dry-run`で検証 → `make load-db DIR=intermediate/<slug>`で登録
- 入力: `text.md`、`sentences.csv`
- 出力: `english_texts`・`sentences`への登録（1トランザクション、`word_count`は自動算出）
- 差し戻し:
  - 検証エラー: 分割・連番・段落不一致 → 02-01、`japanese`空欄 → 03-01
  - タイトル重複: 割り当てありならタイトルを変えず失敗報告（00-01が割り当て直し）。割り当てなしなら01-01でタイトルを変える
  - `relation does not exist`・`column does not exist`: `make db-upgrade`後に再試行

## 中間ファイル（`intermediate/<slug>/`、Git管理外）

| ファイル | 作成 | 形式 |
|---|---|---|
| `text.md` | 01-01 | frontmatter（`title`・`level`・`genre`、すべて必須）＋本文（1行=1段落、空行は無視） |
| `sentences.csv` | 02-01（`japanese`は03-01で更新） | 列: `order_no`（1始まり連番）, `paragraph_no`（1始まり）, `english`, `japanese` |
| `translations.json` | 03-01 | `{"<order_no>": "<和訳>", ...}` |

`text.md`の例:

```
---
title: The Rise of Urban Farming
level: B2
genre: Environment
---
<段落1（1行）>
<段落2（1行）>
```

## パイプラインB: 単語の意味補完

ユーザーから依頼されたとき（「意味を埋めて」等）に`10-01-fill-meanings`（Skill）を手動実行。

```
make vocab-pending
  │ meaning IS NULL かつ未削除の単語
  ▼
intermediate/meanings/pending.json（単語のJSON配列。0件なら完了）
  │ Skillが意味を生成
  ▼
intermediate/meanings/meanings.json（{"<word>": "<意味>", ...}）
  │ make vocab-apply JSON=intermediate/meanings/meanings.json
  ▼
vocabulary_notebook.meaning（meaningがNULLのままの単語のみ更新）
```

- 意味の書き方: 英和辞書風、品詞なし、複数の意味は「；」区切り、例文の文脈は使わない
- 既に意味がある単語・未登録の単語はskippedとして報告（上書きしない）
