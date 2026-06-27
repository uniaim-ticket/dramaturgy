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

インストールすると `dra`（および正式名 `dramaturgy`）コマンドが使えます。いずれかを選びます。

```bash
# A) 仮想環境（推奨。システムに影響しない）
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
dra --version

# B) pipx（隔離環境でPATHに登録）
pipx install -e .

# C) ユーザーインストール
pip install -e . --user
```

Debian/Ubuntu など PEP 668（externally-managed）環境では、素の `pip install` は
ブロックされます。A または B を使うか、`--user` に `--break-system-packages` を付けます。

```bash
pip install -e . --user --break-system-packages
```

`dra` を入れたのに「command not found」になる場合は、インストール先の bin ディレクトリが
`PATH` にありません。`--user` インストールなら次を追加します。

```bash
export PATH="$(python3 -m site --user-base)/bin:$PATH"   # 例: ~/.local/bin
```

**インストールなしの代替** — リポジトリのルートからは、モジュールとして常に実行できます
（インストールもPATH変更も不要）。

```bash
python3 -m dramaturgy --version
python3 -m dramaturgy serve --repo-root /path/to/target
```

以降のコマンドの `dra` は `python3 -m dramaturgy` に読み替えてください。

## 使い方 — Web UI（推奨）

```bash
dra setup --repo-root /path/to/target      # ui_lang / content_lang / project を設定
dra serve --repo-root /path/to/target      # http://127.0.0.1:5178/app/ を開く
```

ブラウザでは、上部の **「Claudeで一括初期化」** が最短経路です。全工程（解析 →
領域ツリー → 領域カード → 統合 → 検査 → HTML生成）を1つのジョブとして実行し、進捗を
逐次表示します（経過時間・ClaudeのプロセスID・CPU/メモリ使用量を表示し、セッションが
生きていることが分かります）。一時的なClaude APIエラーは自動でリトライし、なお失敗した
領域はスキップして報告するので、部分的な地図が得られ、後から個別に補完できます。完了後は
同じセッションのまま、各ステップを個別に調整できます。

または手動で次の順に進めます。

1. **解析** — リポジトリのファイル/ディレクトリを索引（機械処理、Claude不要。
   テーブルやルートの推測はしません）。
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
/dramaturgy:analyze        # リポジトリのファイル/ディレクトリ索引（意味抽出なし）
/dramaturgy:tree           # Claude がソースを読み area-tree.json を作成
/dramaturgy:cards [id]     # Claude がファイルを読み area-maps/<id>.json を作成
/dramaturgy:finalize       # merge + validate + render
```

## コマンド一覧（スクリプト用・内部）

入口は `setup` と `serve`。残りはWeb UI／スラッシュコマンドが内部で呼ぶ機械的ステップで、
スクリプトからも利用できます。

| コマンド | 役割 |
| --- | --- |
| `dra setup` | `.dramaturgy/config.json`（言語・プロジェクト）を作成 |
| `dra serve` | Web UIを起動。Claude Codeを駆動し編集をJSONへ書き戻す |
| `dra analyze-repo` | ファイル/ディレクトリの索引のみ（パス・行数）。意味抽出はしない |
| `dra tree-prompt` | `content_lang` の領域ツリープロンプトを生成 |
| `dra pack` | 1領域の関連ファイルを列挙（Claudeが読む用）、過大なら警告 |
| `dra subdivide` | 自然な子領域案を提示（自動分割はしない） |
| `dra merge` | 領域マップを統合し、重複ID・揺れ・孤立を検出 |
| `dra validate` | 機械的整合性＋言語不変条件の検査 |
| `dra render` | `meaning-map.json` を単一HTMLに描画 |

## 方針

- 機械処理が集めるのは**信頼できる事実のみ**（ファイル/ディレクトリの目録）。テーブル・
  エンティティ・ルート・役割などは推測しません。それらはフレームワークやORMに依存するため、
  **Claudeが実際のソースを読んで**発見します。過大な領域は「自動分割」ではなく「自然な
  下位領域案」として扱います。
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
