# 意味地図ツール (Meaning Map)

大規模な既存システムから、人間が短時間で全貌を理解できる**意味地図**を、
Claude Code の中から生成するためのツール群です。CLIは材料集めと機械検査を担当し、
意味判断（領域の境界・命名・概念への圧縮）はClaudeが行います。正本は
`area-tree.json` と `meaning-map.json` で、HTMLは生成物です。

English version: [README.md](README.md)

## 多言語設計

言語は独立した2層で扱います（混在可）。

| 層 | 設定 | 対象 |
| --- | --- | --- |
| UI / CLI | `ui_lang` | CLIメッセージ・HTMLの固定文言（ラベル・ナビ）＝操作者の言語 |
| コンテンツ | `content_lang` | 生成される意味地図本体とClaude向けプロンプト＝解析対象に合わせる言語 |

対応言語は **`ja`** と **`en`**。正本JSONは1つの `content_lang` のみを保持し、
別言語が必要なら `content_lang` を変えて再生成します（多言語フィールドは持ちません）。
言語の追加は、メッセージカタログとプロンプトテンプレートの追加だけで完結し、
コード変更は不要です。

## 必要環境

Python 3.10 以降（標準ライブラリのみ。外部依存なし）。

## クイックスタート

```bash
# 0. ui_lang / content_lang / project を設定し .meaning-map/config.json を作成
python tools/meaning_map/setup.py --ui-lang ja --content-lang ja \
  --project-name "My System" --repo-root /path/to/target

# 1-3. 材料を集める
python tools/meaning_map/analyze_repo.py            --repo-root /path/to/target
python tools/meaning_map/analyze_schema.py --schema /path/to/target/db/schema.sql
python tools/meaning_map/propose_area_candidates.py --repo-root /path/to/target

# 4. プロンプトを生成し、Claudeに area-tree.json を作らせる
python tools/meaning_map/build_area_tree_prompt.py  --repo-root /path/to/target
#    -> .meaning-map/prompts/area-tree.md （Claudeで実行し area-tree.json を保存）

# 5. 領域ごとにパックを作り、Claudeに領域マップJSONを作らせる
python tools/meaning_map/build_area_pack.py --area-id sales --repo-root /path/to/target
python tools/meaning_map/suggest_subdivision.py --area-id sales --repo-root /path/to/target  # 大きすぎる場合

# 6-8. 統合・検査・HTML生成
python tools/meaning_map/merge_maps.py .meaning-map/area-maps/*.json --repo-root /path/to/target
python tools/meaning_map/validate_map.py --repo-root /path/to/target
python tools/meaning_map/render_html.py  --repo-root /path/to/target
```

各CLIは `--ui-lang` / `--content-lang`（生成系のみ）/ `--repo-root` で
config.json の値を都度上書きできます。

## ツール一覧

| ツール | 役割 |
| --- | --- |
| `setup.py` | `.meaning-map/config.json`（言語・プロジェクト）を作成 |
| `analyze_repo.py` | ソースの索引（ファイル・役割・ルート・テーブル候補） |
| `analyze_schema.py` | SQL DDL からテーブル・外部キー・状態カラムを抽出 |
| `propose_area_candidates.py` | 候補材料（ディレクトリ・FKグラフ・APIプレフィックス） |
| `build_area_tree_prompt.py` | `content_lang` の領域ツリープロンプトを生成 |
| `build_area_pack.py` | 1領域の関連ファイル・テーブル・APIを収集、過大なら警告 |
| `suggest_subdivision.py` | 自然な子領域案を提示（自動分割はしない） |
| `merge_maps.py` | 領域マップを統合し、重複ID・揺れ・孤立を検出 |
| `validate_map.py` | 機械的整合性＋言語不変条件の検査 |
| `render_html.py` | `meaning-map.json` を単一HTMLに描画 |

## 方針

- CLIは材料集めと機械検査、**意味判断はClaude**。過大な領域は「自動分割」ではなく
  「自然な下位領域案」として扱います。
- 中間JSONは整形済みUTF-8で出力し、Git差分でレビューしやすくします。
- `validate_map.py` が言語不変条件を検査します（対応コードか、`content_lang` が
  config と一致するか、カタログのキー欠落がないか）。

## 開発

```bash
python -m unittest discover tests        # または: python -m pytest tests/
```

## ライセンス

MIT — [LICENSE](LICENSE) を参照。
