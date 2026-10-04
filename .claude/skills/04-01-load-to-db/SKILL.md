---
name: 04-01-load-to-db
description: intermediate/<slug>/のtext.mdとsentences.csvを検証し、`make load-db`でenglish_texts・sentencesテーブルへ登録する。03-01-translate完了後、パイプラインAの最終ステップとして使う。
---

# Skill: DB登録

## ⚠️ 厳守事項
- 登録済み記事を上書き・再登録しない（単語帳の`sentence_ids`から参照されるため）。同タイトル（削除済みを除く）の記事はProgramが拒否する。
- DB接続は`config/settings.local.toml`の`[db] connection_string`を使う。その内容を出力・記載しない。
- DBを直接SQLで更新しない。

## 目的
完成した記事と文・訳を、`english_texts`（記事）と`sentences`（文）へ1トランザクションで登録する。

## 入出力
- 入力: `intermediate/<slug>/text.md`、`intermediate/<slug>/sentences.csv`
- 出力: DBの`english_texts`・`sentences`テーブル（`word_count`は英文全文からProgramが自動算出）

## Program内の検証内容
- `order_no`が1始まりの連番
- `paragraph_no`の段落数が`text.md`と一致
- 各段落の`english`連結が`text.md`の該当段落と一致
- `english`・`japanese`に空欄なし
- 登録時: 同タイトル（削除済みを除く）の記事が無いこと

## 手順
1. DB非接続で検証する

   ```bash
   make load-db DIR=intermediate/<slug> ARGS=--dry-run
   ```

2. 検証OKなら登録する

   ```bash
   make load-db DIR=intermediate/<slug>
   ```

## エラー時の対応
- 検証エラー: 原因に応じて該当ステップへ戻る（分割・連番・段落不一致 → `02-01-split-sentences`、`japanese`空欄 → `03-01-translate`）。
- タイトル重複: `01-01-generate-text`へ差し戻す。00-01の割り当てで実行中ならタイトルを変えず失敗として報告し、割り当てが無ければタイトルを変える（テーマも重複していれば記事自体を作り直す）。
- `relation does not exist`・`column does not exist`: この場合のみ`make db-upgrade`を実行し、手順2から再試行する。
- 接続エラー: `config/settings.local.toml`の`[db]`設定を確認する（値は出力しない）。

## 完了条件・報告
`make load-db`（`--dry-run`なし）が正常終了した時点で完了。`english_texts.id`、タイトル、レベル、ジャンル、`word_count`、文数を報告する。

完了条件を満たしていれば確認を挟まず次のSkillへ進む。満たしていない場合は本Skill内の該当手順（またはエラー時の対応）からやり直す。完了条件は満たしているが判断に迷う点・懸念がある場合のみ、その旨を添えて人間に相談する。

## 次のSkill
なし（パイプラインA完了）。
