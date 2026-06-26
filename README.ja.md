# dramaturgy

大規模な既存システムから、人間が短時間で全貌を理解できる**意味地図**を生成します。
機械的な処理（索引・検査・HTML描画）はスクリプトが担い、意味判断（領域の境界・命名・
概念への圧縮）は **Claude Code** が行います。正本は `area-tree.json` と
`meaning-map.json` で、HTMLは生成・編集可能なビューです。

解析を手で叩くことはありません。次のいずれかで進めます。

- **ローカルWeb UI**（`dra serve`）でツリー/カードを閲覧・編集し、必要なときに
  Claude Code を呼び出す、または
- **Claude Code の中**から同梱のカスタムコマンド
  （`/dramaturgy:analyze` / `:tree` / `:cards` / `:finalize`）で進める。

English version: [README.md](README.md)

## 仕組み

Web UI（`dra serve`）は Claude Code をヘッドレスのサブプロセスとして起動します
（`claude -p … --output-format stream-json --permission-mode acceptEdits`）。これは
[requirements-reviewer](https://github.com/uniaim-ticket/requirements-reviewer)
と同じ方式です。Claude が JSON 成果物を直接書き込み、UIは JSON から HTML を再描画し、
カードの編集を **JSON へ書き戻し** ます。

```
正本: .dramaturgy/area-tree.json / .dramaturgy/meaning-map.json
   ▲           ▲
   │ 書き戻し   │ Claudeが生成
   │           │
 Web UI ──呼出──▶ Claude Code（領域ツリー/領域カードを生成）
   │
   └─ 機械的CLI: analyze / merge / validate / render（意味判断はしない）
```

## 多言語設計

言語は独立した2層で扱います（混在可）。

| 層 | 設定 | 対象 |
| --- | --- | --- |
| UI / CLI | `ui_lang` | CLIメッセージ・Web UIの固定文言・HTMLラベル＝操作者の言語 |
| コンテンツ | `content_lang` | 生成される意味地図本体とClaude向けプロンプト＝解析対象に合わせる言語 |

対応言語は **`ja`** と **`en`**。正本JSONは1つの `content_lang` のみを保持し、別言語が
必要なら `content_lang` を変えて再生成します（多言語フィールドは持ちません）。

## 必要環境

- Python 3.10 以降（標準ライブラリのみ。外部依存・ビルド工程なし）。
- 生成ステップ用に [Claude Code](https://claude.com/claude-code) CLI（`claude`）が
  PATH 上にあること。

## インストール

```bash
pip install -e .        # `dra`（および `dramaturgy`）コマンドを登録
```

`dra` と正式名 `dramaturgy` は同じCLIに解決されます。インストールせずに
`python -m dramaturgy` でも実行できます。

## 使い方 — Web UI（推奨）

```bash
dra setup --repo-root /path/to/target      # ui_lang / content_lang / project を設定
dra serve --repo-root /path/to/target      # http://127.0.0.1:5178/app/ を開く
```

ブラウザで次の順に進めます。

1. **解析** — リポジトリを索引（機械処理、Claude不要）。
2. **領域ツリー** — *Claudeで生成*: Claude が `area-tree.json` を書き込みます。
   JSONをその場で編集して保存し直せます。
3. **領域カード** — 領域ごとに *Claudeで生成*: Claude が各 `area-maps/<id>.json` を
   書き込みます。
4. **統合・表示** — merge / validate / render。領域のフィールドを編集して保存すると、
   その変更は **`meaning-map.json` へ書き戻され**、プレビューが更新されます。

## 使い方 — Claude Code の中

このリポジトリの `.claude/commands/` が使える状態で、解析対象リポジトリ上の
Claude Code セッションで実行します。

```
/dramaturgy:analyze        # リポジトリ索引（dra analyze-* + candidates を実行）
/dramaturgy:tree           # Claude が .dramaturgy/area-tree.json を作成
/dramaturgy:cards [id]     # Claude が area-maps/<id>.json を作成（省略時は全領域）
/dramaturgy:finalize       # merge + validate + render
```

## コマンド一覧（スクリプト用・内部）

入口は `setup` と `serve`。残りはWeb UI／スラッシュコマンドが内部で呼ぶ機械的ステップで、
スクリプトからも利用できます。

| コマンド | 役割 |
| --- | --- |
| `dra setup` | `.dramaturgy/config.json`（言語・プロジェクト）を作成 |
| `dra serve` | Web UIを起動。Claude Codeを駆動し編集をJSONへ書き戻す |
| `dra analyze-repo` | ソースの索引（ファイル・役割・ルート・テーブル候補） |
| `dra analyze-schema` | SQL DDL からテーブル・外部キー・状態カラムを抽出 |
| `dra candidates` | 候補材料（ディレクトリ・FKグラフ・APIプレフィックス） |
| `dra tree-prompt` | `content_lang` の領域ツリープロンプトを生成 |
| `dra pack` | 1領域の関連ファイル・テーブル・APIを収集、過大なら警告 |
| `dra subdivide` | 自然な子領域案を提示（自動分割はしない） |
| `dra merge` | 領域マップを統合し、重複ID・揺れ・孤立を検出 |
| `dra validate` | 機械的整合性＋言語不変条件の検査 |
| `dra render` | `meaning-map.json` を単一HTMLに描画 |

## 方針

- スクリプトは材料集めと機械検査、**意味判断はClaude**。過大な領域は「自動分割」ではなく
  「自然な下位領域案」として扱います。
- 正本はJSON。HTMLは生成ビューで、UI上の編集はJSONへ書き戻します。中間JSONは整形済み
  UTF-8で出力し、Git差分でレビューしやすくします。
- `dra validate` が言語不変条件を検査します（対応コードか、`content_lang` が config と
  一致するか、カタログのキー欠落がないか）。
- サーバは `127.0.0.1` のみにバインドします（ローカル単一利用者向けツール）。

## 開発

```bash
python -m unittest discover tests        # または: python -m pytest tests/
```

## ライセンス

MIT — [LICENSE](LICENSE) を参照。
