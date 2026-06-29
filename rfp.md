# 意味地図生成ツール 作成指示書 改訂版

## 前提

このツール群は、Claude Code の中から呼び出して使う。

Claude Code がリポジトリを読み、必要に応じてローカルCLIツールを実行し、その結果をもとに「意味地図」を作成・検証・更新する。

重要なのは、機械的な分量分割ではなく、人間が見て自然な業務・概念・構造単位で分割することである。

## 公開・多言語対応の方針

このツール群は OSS として公開する前提で作成する。したがって、特定のリポジトリ・組織・言語に依存した値をコードへ直接埋め込まない。プロジェクト固有の値はすべて設定ファイル経由で受け取る。

### 言語に関する二層モデル

言語は2つの層に分けて扱う。両者は独立に設定でき、混在を許す（例: UIは日本語、生成内容は英語）。

```text
1. UI/CLI言語 (ui_lang)
   - CLIの進捗メッセージ・警告・エラー
   - HTMLのラベル・ナビゲーション・固定文言(chrome)
   - 操作者(=このツールの利用者)が読む言語

2. 生成内容言語 (content_lang)
   - Claudeが生成する意味地図そのものの言語
     (領域名・一言説明・概念・フロー・注意点など)
   - 解析対象システムに合わせて選ぶ言語
   - Claudeへ渡すプロンプトも content_lang に応じて切り替える
```

* 対応言語は日本語 (`ja`) と英語 (`en`) の2つ。
* 既定の参照実装言語は日本語とするが、英語も一定品質を維持する。
* UI/CLI文言とプロンプトは、コードに直書きせずメッセージカタログ／テンプレートとして言語別に分離する。新しい言語の追加がカタログ追加だけで済む構造にする。

### セットアップ時の言語設定

初回セットアップ時に `ui_lang` と `content_lang` を設定させ、設定ファイルへ保存する。以後のCLI・HTML生成は原則この設定を既定値として参照する。各コマンドは `--ui-lang` / `--content-lang` で都度上書きできる。

```text
.dramaturgy/config.json
```

```json
{
  "schema_version": 1,
  "ui_lang": "ja",
  "content_lang": "ja",
  "project": {
    "name": "",
    "repo_root": "."
  }
}
```

### 単一言語・再生成モデル

意味地図の中間成果物 (`area-tree.json` / `meaning-map.json`) は、1回の生成につき1つの `content_lang` のみを格納する単一言語スキーマとする。

* 別言語版が必要な場合は `content_lang` を変えて再生成する。多言語フィールド (`name_ja` / `name_en` など) は持たせない。
* 正本JSONには、その内容が何語かを示す `content_lang` を必ず記録する（後述のスキーマ参照）。
* HTMLの固定文言(chrome)だけは `ui_lang` に従ってカタログから差し込む。本文コンテンツは正本JSONの `content_lang` のまま表示する。

### 品質維持

* 日本語・英語いずれの `content_lang` でも、プロンプトは同等の指示密度を保つ（片方だけ詳細にしない）。
* UI/CLIメッセージは全言語でキーの欠落がないことを機械検査する（後述 `validate_map.py` / カタログ検査）。
* 公開リポジトリには日本語・英語両方の README を用意する。

## 目的

大規模な既存システムから、人間が短時間で全貌を理解できる「意味地図」を生成する。

意味地図は詳細仕様書ではなく、以下を満たす圧縮された理解支援資料である。

* 全体像が少量で把握できる
* 業務領域の関係がわかる
* 登場人物ごとに誰が何をするかがわかる
* 概念Entityと業務フローの関係がわかる
* 開発者がコード・DB・API・画面との対応を確認できる
* 展開すると次の詳細概念に辿れる
* Claude による妥当性検査を行える

## 最重要方針

領域分割は、以下の順で行う。

```text
1. 人間が見て自然な業務・概念・責務で分ける
2. 次に、コード構造・DB構造・API構造との対応を見る
3. そのうえで、1領域が大きすぎる場合だけ下位領域に細分化する
4. トークン数やファイル数は補助指標であり、主基準ではない
```

悪い分割例:

```text
- ファイル数が多いから半分に割る
- ディレクトリが違うから必ず別領域にする
- 10万トークンを超えたから意味を無視して切る
- テーブル名をそのまま業務領域にする
```

良い分割例:

```text
チケット販売
  ├─ 申込
  ├─ 抽選
  ├─ 決済
  ├─ 発券
  └─ 入場

イベント管理
  ├─ 公演
  ├─ 席種
  ├─ 価格
  └─ 在庫

会計
  ├─ 売上
  ├─ 前受金
  ├─ 返金
  └─ 精算
```

## 領域分割の基準

優先順位は以下。

### 第1基準: 業務上の自然さ

* 業務担当者がその単位で話すか
* 利用者・管理者の行動単位として自然か
* 1つの目的を持っているか
* 入口と出口が説明できるか
* 関連する状態遷移がまとまっているか

### 第2基準: 概念上のまとまり

* 同じ概念Entityを中心としているか
* 同じライフサイクルを扱っているか
* 同じ状態を共有しているか
* 同じイベント系列に属しているか

### 第3基準: 実装上のまとまり

* 関連するAPI、画面、テーブル、モデルがまとまっているか
* コード上の責務境界と大きく矛盾しないか
* 変更時に一緒に読まれることが多そうか

### 第4基準: 分量

* 1領域が大きすぎる場合だけ細分化する
* 目安として Claude に渡す1パックは10万トークン程度以下を目指す
* ただし、意味的に切れないものを無理に分割しない
* 大きすぎる場合は「親領域 + 子領域」にする

## ツリー構造の考え方

領域は必ずツリーとして整理する。

```text
system
  ├─ area
  │   ├─ sub_area
  │   └─ sub_area
  └─ area
      ├─ sub_area
      └─ sub_area
```

親領域は「人間が全体像を理解するための単位」とする。

子領域は「詳細を見るための単位」とする。

親領域には詳細を詰め込みすぎない。

例:

```yaml
id: ticket_sales
name: チケット販売
one_liner: 利用者がチケットを申し込み、支払い、利用可能な状態にする領域
child_area_ids:
  - ticket_sales.application
  - ticket_sales.lottery
  - ticket_sales.payment
  - ticket_sales.ticketing
  - ticket_sales.admission
```

## 実行モデル（重要）

このツールはユーザーが個別のPythonスクリプトを手で叩く方式ではない。実行主体は次の2つで、どちらも**意味判断は Claude Code が行い、機械処理はスクリプトが行う**。

### 方式A: ローカルWeb UI（既定）

`dra serve` でローカルWebサーバ（`127.0.0.1` のみ）を起動し、ブラウザUIで意味地図を閲覧・レビューする。requirements-reviewer (rr) と同じ考え方で、HTML/JSON成果物を中心に据える。

UIは **地図プレビュー（主役）＋レビューキュー** の2ペイン構成とし、生成→ツリー→カード→統合といった工程別の画面は持たない（それらは一括初期化に隠蔽する）。

* **開発者モードの切替**: 地図には非開発者（業務担当者）も読む前提の項目と、開発者向けの項目が混在する。ヘッダーのトグルで開発者向け項目をまとめて表示/非表示する。既定は非表示（非開発者向け）。設定はクライアント（localStorage）に保持し、再読込でも維持する。
  - 非開発者には隠す項目: 領域カードの関連コード(code_refs)・関連API・関連画面、検証結果(validation)セクションとそのナビゲーション、および生成系の操作（追加指示・一括初期化・言語選択と保存）。
  - 開発者モードに関わらず使える: 地図の閲覧（登場人物・概念データ・区分・業務領域・CRUD・構成）と**指摘キュー**。
  - 実装: プレビューHTMLは開発者向け項目を `dev-only` クラス付きで常に出力し、`body.dev` の有無でCSS表示を切り替える（再生成不要）。親アプリは iframe へ初期状態を `?dev=1` クエリで渡し、トグル時は `postMessage`（`source: dramaturgy-shell`）で即時反映する。アプリ側の開発者向けヘッダー操作も同じ `dev-only` クラスで切り替える。

流れは:

1. ヘッダーの**一括初期化**ボタンで、`analyze → ツリー生成(Claude) → 子領域レビュー(Claude) → 各領域カード生成(Claude) → merge → validate → 目的記述(Claude) → render` を1つのジョブとして順に実行する（カード生成・子領域レビュー・目的記述は `--resume` で同一セッションを引き継ぐ）。
   - **目的記述**: 完成した地図を踏まえ、Claude がシステム全体の目的・概要（system.purpose, 1000文字以内）を最後に書く。全体像が出そろってから書くのが自然なため最後に行う。失敗しても致命的ではない（目的なしで地図は完成し、HTMLでは当該セクションを省く）。
   - **子領域レビュー**: 初回ツリーのうち、大きすぎる／直接関係のない複数の責務を1領域に抱えた領域だけを、Claudeが自然な子領域に分割し area-tree.json を更新する（親領域はそのまま残し `child_area_ids` を付与、子領域を新規エントリとして追加）。初回生成では子領域を作らなくてよいが、分割した方がよいと判明した領域だけここで分割する。不要なら何もしない。続くカード生成は分割後ツリーに対して行うので子領域カードも生成される。領域階層の正本は area-tree.json なので、merge 後に親子関係（parent/child）を area-tree.json から meaning-map.json へ上書きし、カードが階層を省いても地図に反映されるようにする。
   - **解析指示設定（追加指示）**: コード母体に関するシステム固有の指示（例: マスタ/トランザクションの区分をタグ付け）を入力でき、ツリー生成・子領域レビュー・カード生成の各プロンプトに差し込む。指示は結果データと別ファイル `.dramaturgy/init-instructions.txt` にリポジトリ単位で保存し、再実行のたびに再利用する（過去の結果データそのものは参照しない）。同じ場所で **Claudeの思考量（effort: low/medium/high/xhigh/max、既定 xhigh）** も指定でき、`.dramaturgy/init-effort.txt` に保存して全体解析・各指摘処理に適用する。
2. 左のプレビューを読む（登場人物を先頭に、概念データ・業務領域・CRUD）。
3. プレビュー内の各項目（登場人物・概念データ・業務領域、および各フィールド/行）の **＋** から**インラインで指摘**を付け、キューに積む。
4. 積まれた指摘はサーバのワーカーが**自動で順番に実行**する（ユーザーは実行・停止を操作しない）。右のキューに状態と進捗が出る。

* 重い意味判断（領域ツリー生成・領域カード生成・各指摘の処理）は、UIから **Claude Code をヘッドレス起動**して実行する:
  `claude -p "<prompt>" --output-format stream-json --permission-mode acceptEdits --add-dir <repo> [--effort <level>]`
* `acceptEdits` を既定にするのは、ヘッドレス実行では対話的な許可応答ができないため。Claude がワークスペース内のJSONを直接書き込めるようにする。
* **思考量（effort）**: Claude Code の `--effort`（low/medium/high/xhigh/max）をリポジトリ単位で
  指定できる。既定は `xhigh`。解析指示設定（追加指示）と同じ場所で設定・保存し、全体解析と各指摘の
  処理の両方に適用する。`.dramaturgy/init-effort.txt` に保存する。
* 進捗は stream-json をパースし、UIは**ポーリング**で表示する（バッファリングするプロキシでも止まらないため）。
* セッションIDを保持し、追撃の指示や指摘処理は `--resume` で文脈を引き継ぐ（継続/新規は都度選択）。
* インライン指摘は、プレビュー(iframe)内の `+` クリックを `postMessage` で親アプリに伝え、親がポップオーバーを開いて発行する。

### 方式B: Claude Code のカスタムコマンド

解析対象リポジトリ上の Claude Code セッションで、同梱のカスタムコマンドを使う。

```text
/dramaturgy:analyze    ファイル/ディレクトリ目録（意味抽出なし）
/dramaturgy:tree       Claude がソースを読み area-tree.json を作成
/dramaturgy:cards [id] Claude がファイルを読み area-maps/<id>.json を作成
/dramaturgy:finalize   merge + validate + render
```

### 書き戻し（双方向）

* 正本は `area-tree.json` / `meaning-map.json`。HTMLは生成ビュー。
* Claude Code は意味判断の結果を正本JSONへ直接書き込む。
* Web UI 上の人間の編集（領域名・一言説明・注意点など）は、API経由で正本JSONへ**書き戻す**（`PUT /api/artifact/<name>`、`PATCH /api/area/<id>`）。生JSON編集と構造化フィールド編集の両方を許す。
* どちらの経路で編集しても、HTMLは正本JSONから再描画される。

### 対話的レビュー（3種類の指摘）

生成後の調整は、項目ごとの**個別の対話的修正**で行う（requirements-reviewer と同様）。
対象は登場人物・概念データ・業務領域の各エントリ。人間は対象を指して**指摘（finding）**を
付け、Claude に実行させる。よく使う入口は登場人物からの編集である。

指摘は次の3種類に分類し、処理と反映先を変える:

```text
reframe（再整理）  指摘を是として捉え方を整理し直す → 正本 meaning-map.json を直接編集
audit  （検査）    正本は変えず、既存と矛盾しないか・説明できないパターンがないか調査
                   → audits/<id>.json に結果を記録
proposal（将来提案）今後こう変更したい、を現状とは別に記録 → proposals/<id>.md
```

* 指摘は `.dramaturgy/reviews.json` に永続化する（`{id, target_type, target_id,
  field, field_label, kind, comment, status, job_id, session_id, result,
  audit_result, proposal_ref}` と `settings`）。
* キューに積まれた指摘は**単一のバックグラウンドワーカー**が古い順に1件ずつ自動実行する。
  ユーザーは実行・停止を管理しない。完了/エラーの指摘は「再実行」で再キューできる。
  サーバ再起動時に `running` のまま残った指摘は `open` に戻して再実行する。
* **Claudeセッションを継続するか新規にするか**はサーバ設定（`settings.continue_session`、
  既定 true）で、ワーカーが参照する（継続なら直近のレビューセッションを `--resume`）。
* reframe のみ as-is 正本を書き換える。audit / proposal は as-is を汚さず別ファイルに残す。
* `field` を持つ指摘は対象の特定の要素（フィールド/行）にスコープされる。

## Claude Code 内での使い方

Claude Code は以下のように進める。

```text
0. セットアップ: ui_lang / content_lang / project を設定し config.json を作る
1. リポジトリのファイル/ディレクトリ目録を作成する（意味抽出なし）
2. Claude がソースを読み、自然な業務領域ツリー(area-tree.json)を作る
3. 子領域レビュー: 大きすぎる／責務が混在する領域だけ、Claude が子領域に分割する（不要なら何もしない）
4. 各領域（分割後の子領域を含む）について、Claude が関連ファイルを読み意味地図カードを生成する
5. JSONを統合する（merge）
6. 機械的整合性を検査する（validate）
7. 仕上げ: Claude が完成した地図を踏まえ、システム全体の目的（system.purpose, 1000文字以内）を書く
8. HTMLを生成する（render）
```

目的（system.purpose）は全体像が出そろってから書くのが自然なので、生成パイプラインの**最後**
（merge/validate 後、render 前）に行う。失敗しても致命的ではない（目的なしで地図は完成する）。

ステップ0以降のCLIは、引数で言語を明示しない限り config.json の `ui_lang` / `content_lang` を既定値として使う。

## CLIツールの役割

CLIツールは、意味判断を主導しない。

**重要な原則: 機械処理は「信頼できる事実」の収集だけに限定する。** テーブル・エンティティ・
API・ルート・役割などの意味的事実は、フレームワークやORM・マイグレーション・規約に依存し、
正規表現などで機械的に正しく抽出することはできない。中途半端な抽出は誤った材料を生み、
Claudeの判断を誤らせる。したがってそれらは抽出せず、**Claude がリポジトリのソースを実際に
読んで発見する**（Claude Code はファイルアクセスを持つ）。CLIが集めてよいのは、ファイル一覧・
拡張子・行数・ディレクトリ集計といった、機械的に確実に分かる目録のみである。

必要なCLIは以下。すべてのCLIは共通で `--ui-lang {ja|en}` を受け取り、進捗・警告・エラーをその言語で出力する。生成系CLIはさらに `--content-lang {ja|en}` を受け取る。いずれも省略時は config.json の値を使う。

### コマンド体系

ツール名は `dramaturgy`、短縮コマンドは `dra`（両者は同一CLIに解決する）。各機能は個別スクリプトではなく `dra <サブコマンド>` として提供する。`dra --help` で一覧、`dra <サブコマンド> --help` で個別オプションを表示する。以下の各節は機能単位で、見出しの括弧内が対応するサブコマンド名である。

```text
setup           初期セットアップ（config.json 生成）
analyze-repo    ファイル/ディレクトリ目録（意味抽出なし）
tree-prompt     領域ツリープロンプト生成
pack            領域のファイル一覧生成（Claudeが読む用）
subdivide       子領域案の提示
merge           領域マップ統合
validate        機械的整合性＋言語不変条件の検査
render          HTML生成
export-parts    部分参照用の map-index.json + parts/ を正本から派生（読み取り専用）
```

### 0. setup（`dra setup`）

目的:

* 初回セットアップを行い、`.dramaturgy/config.json` を生成する。

役割:

* `ui_lang` / `content_lang` / `project.name` / `project.repo_root` を対話または引数で受け取る。
* 既存の config.json がある場合は値を尊重し、不足項目だけ補う。
* 対応外の言語コードが渡された場合はエラーにする。

```bash
dra setup \
  --ui-lang ja \
  --content-lang ja \
  --project-name "My System" \
  --repo-root .
```

出力:

```text
.dramaturgy/config.json
```

### 1. analyze-repo（`dra analyze-repo`）

目的:

* リポジトリのファイル/ディレクトリ目録を作る（意味抽出はしない）。

出力:

```text
.dramaturgy/source-index.json
```

収集するもの（機械的に確実に分かるもののみ）:

* ファイル一覧（パス・拡張子・行数）
* 拡張子別の集計
* ディレクトリ別のファイル数・行数集計
* 分析対象の素性 `source_meta`（機械的に確実に分かる事実のみ）:
  ルートに LICENSE/COPYING があるか（= 公開リポジトリとみなす `public` フラグ）、
  git リモートURL（`repo_url`、SSH形式はhttpsへ正規化）、分析時点のコミット（`commit` /
  `commit_short`）。git でない・git未導入なら該当項目は省く。

収集しないもの（Claude がソースを読んで発見する）:

* テーブル / エンティティ / カラム / 外部キー
* API / ルート / コントローラ / モデル / マイグレーション / 役割

> 旧版にあった `analyze-schema`（SQL解析）と `candidates`（候補材料生成）は廃止した。
> テーブルは SQL とは限らず（ORM・マイグレーション・規約で定義され得る）、機械抽出は
> 誤りを生むため。これらの発見は Claude がソースを読んで行う。

### 2. tree-prompt（`dra tree-prompt`）

目的:

Claude に自然な領域ツリーを作らせるためのプロンプトを生成する。プロンプトには
ファイル/ディレクトリ目録のみを載せ、Claude には「実際のソースを読んで
テーブル・概念・エンティティを発見せよ」と明示する。

入力:

* source-index.json（ファイル/ディレクトリ目録のみ）

出力:

```text
.dramaturgy/prompts/area-tree.md
```

このプロンプトでは、Claude に以下を要求する。

* 人間が見て自然な業務領域ツリーを作る
* トークン量ではなく概念構造を優先する
* 1領域が大きすぎる場合だけ子領域に分ける
* 各領域に一言説明を付ける
* 登場人物を仮説として整理する
* 主要概念を対応づける
* confidence を付ける

プロンプト本体（指示文）は `content_lang` に応じて言語別テンプレートから生成する。生成物 (`area-tree.json`) の自然言語フィールドは `content_lang` で書くよう明示する。テンプレートは言語間で指示密度を揃える。

### 3. pack（`dra pack`）

目的:

作成済み area-tree.json の各領域について、Claude に渡す分析パックを作る。

重要:

area-tree.json が先にある前提とする。
CLIが勝手にクラスタを決めない。

```bash
dra pack \
  --area-id ticket_sales.application \
  --area-tree .dramaturgy/area-tree.json \
  --source-index .dramaturgy/source-index.json \
  --out .dramaturgy/area-packs/ticket_sales.application.md
```

役割:

* area-tree で指定された領域の source_hints に合致するファイルを集める
* それらを「Claude が読むべきファイル一覧」として渡す
* トークン量（規模）を見積もり、大きすぎる場合は警告する（自動分割はしない）

注意: テーブル/API/画面の抽出はしない。Claude が列挙されたファイルを読んで、
それらを発見する。

### 4. subdivide（`dra subdivide`）

目的:

1領域が大きすぎる場合に、自然な子領域案を出す。

重要:

これは自動分割ではなく、Claude が判断するための補助材料である。

出力するもの:

* 子領域候補
* なぜ自然か
* 関連概念
* 関連ファイル
* 関連テーブル
* 分量見積もり
* 分割しない方がよい理由がある場合はそれも出す

### 5. merge（`dra merge`）

目的:

領域ごとの meaning map を統合する。

役割:

* area-map JSON を統合する
* ID重複検出
* 概念名の揺れ検出
* 関連領域リンク補完
* 親子関係の整合性検査
* 孤立領域の検出

### 6. render（`dra render`）

目的:

meaning-map.json からHTMLを生成する。HTMLは外部アセットに依存しない**単一の完結したファイル**
（CSS・JSはインライン）とする。

* **配布用エクスポート（`dra render --export` / Web UIの「資料を書き出す」 / `GET /api/export`）**:
  同じ意味地図を、レビュー用の **＋** ピンとアプリ連携（postMessage・iframe前提のスクリプト・
  状態復元）を取り除いた**完結した配布用1ファイル**として出力する。非開発者にそのまま渡せる資料に
  なる。開発者向け項目（関連コード・API・画面・検証結果）は、アプリのヘッダーではなくファイル内蔵の
  トグルで表示/非表示する（同じ `dev-only` / `body.dev` 機構を流用）。
  実装方針: 通常ビューとエクスポートは**同一のレンダリングロジックを共有**し、`export` フラグ
  だけで分岐する。ピンの抑止は描画ヘルパ全体に引数を通さず、`render_html` 内のコンテキストで
  `pin()` を空文字にする。重複ロジックを作らない。

HTMLに必要なビュー:

* 分析対象のノート: 公開リポジトリ（`system.source.public` が真＝LICENSEあり）のときだけ、
  最上部に分析対象リポジトリへのリンクと分析時点のコミットハッシュを表示する。非公開や
  情報がない場合は何も出さない。コミットがあればリンクはその版（`/tree/<commit>`）へ、
  コミットハッシュは該当コミット（`/commit/<commit>`）へ張る。
* システムの目的: 先頭（登場人物より前）に、システム全体の目的・概要（system.purpose）を
  短い段落で表示する。書かれていない場合はセクションごと省く。
* 業務領域: まず全領域をボックスで一覧し、クリックで詳細を展開する（「全体地図」のような
  無意味な俯瞰図は作らない）。詳細展開時には、**そのシステムを使ったことがない人でも全体像が
  分かる概要レベルの業務フロー**を**スイムレーン**（縦レーン＝関係する登場人物 actor）で表示する。
  各領域の `overview_flow: {lanes:[actor_id], steps:[{lane, label, use_case}]}` から描画する。
  1領域に直接の関係がない複数ユースケース（例: マスタ申請承認 と バッチ監視）が含まれる場合は、
  図を分けず同一スイムレーン内で `use_case` が変わる箇所に区切り線（＋ユースケース名）を入れ、
  ステップ番号はユースケースごとに振り直す。
* 概念データ: 物理テーブルを業務的意味でまとめた概念データと、それを使う領域の対応
  （各概念に物理テーブル名を併記する）
* CRUD: 業務領域×概念データの組を1つの表で表示する。並び替え（概念データ順／業務領域順）と、
  業務領域・概念データそれぞれの抽出（検索付きの複数選択コンボボックス。未選択＝すべて）ができ、
  各セル末尾の控えめなリンクから該当の業務領域・概念データの表示箇所へ移動できる
* 登場人物ビュー
* 検証結果ビュー

言語の扱い:

* ラベル・ナビゲーション・見出しなどの固定文言(chrome)は `ui_lang` のメッセージカタログから差し込む。
* 本文コンテンツ（領域名・説明・概念など）は meaning-map.json の `content_lang` のまま表示する。
* HTMLには `<html lang="...">` に content_lang を反映し、chromeとコンテンツの言語が異なる場合もある旨を考慮する。

### 6b. export-parts（`dra export-parts`）— 部分参照用の派生

目的:

正本 `meaning-map.json` は全体を1ファイルに持つため「全部読む」には最適だが、ある領域だけ見たい
読者にも全文パースを強いる。そこで**正本から派生する読み取り専用ビュー**を出力し、
別セッションのエージェント（dramaturgyとは無関係に、対象リポジトリで普通に作業している
Claude Code 等）が**必要な分だけ**読めるようにする。

* `map-index.json`（数十KB）: システムの目的、領域ツリー（id/name/one_liner/親子）、概念・登場人物の
  一覧。各エントリに `part`（部分ファイルのパス）と `bytes`（サイズ目安）を付け、全体把握と
  「どのpartを開くか」の判断を軽量に行えるようにする。
* `parts/areas/<id>.json`: 領域単位の**自己完結**カード。触れる概念の名前・物理テーブル、登場人物名、
  関連する区分を解決して同梱するので、その1ファイルだけで作業判断できる。
* `parts/concepts/<id>.json`: 概念単位のカード（使用領域名とCRUDを解決）。
* `parts/README.md`: ディレクトリの読み方を人間/エージェント向けに説明する。

重要な原則:

* 正本は依然 `meaning-map.json` 一本。`map-index.json` と `parts/` は**派生・読み取り専用**で、
  merge / render のたびに正本から再生成するため陳腐化しない。手編集は正本に対してのみ行う。
* 派生は `render`（一括初期化の末尾、reframe反映後の再描画、UI/HTTPの各書き戻し）で自動更新する。
  生成途中の `area-maps/<id>.json` は初回生成の中間物であり、部分参照の正本としては使わない
  （編集が反映されないため）。

### 7. validate（`dra validate`）

目的:

機械的に検査できる整合性を確認する。

検査内容（機械的に確実に検査できるもののみ）:

* 参照先ファイル（code_refs）が存在するか
* CRUD対象が concepts に存在するか（id 形のキーのみ）
* parent_area_id / child_area_ids が一致しているか
* related_area_ids が存在するか
* 循環参照がないか
* confidence: low の項目が一覧化されているか
* config.json の `ui_lang` / `content_lang` が対応言語か
* meaning-map.json / area-tree.json に `content_lang` が記録され、config と一致するか
* UI/CLIメッセージカタログに全対応言語ぶんのキーが揃っているか（欠落キーの一覧化）

検査しないもの: テーブル名やAPI名の「存在」。これらは機械的な正本リストを持たない
（Claude がソースを読んで発見する）ため、照合先がない。

## Claude が主導する判断

以下はCLIではなくClaudeが判断する。

* 業務領域名
* 領域の境界
* 親子領域の自然さ
* 業務上一言でどう説明するか
* 登場人物の整理
* DBテーブルから概念Entityへの圧縮
* フローの意味づけ
* CRUDの業務的意味
* リスクポイント
* 「これは分けるべきか、同じ領域にすべきか」

## area-tree.json のスキーマ

```json
{
  "content_lang": "ja",
  "system": {
    "name": "",
    "summary": ""
  },
  "areas": [
    {
      "id": "",
      "name": "",
      "one_liner": "",
      "purpose": "",
      "parent_area_id": null,
      "child_area_ids": [],
      "related_area_ids": [],
      "primary_actors": [],
      "primary_concepts": [],
      "source_hints": {
        "directories": [],
        "tables": [],
        "apis": [],
        "screens": [],
        "keywords": []
      },
      "split_reason": "",
      "confidence": "high|medium|low"
    }
  ]
}
```

## meaning-map.json のスキーマ

```json
{
  "content_lang": "ja",
  "system": {
    "name": "",
    "summary": "",
    "purpose": "",
    "generated_at": "",
    "source": {
      "public": false,
      "repo_url": "",
      "commit": "",
      "commit_short": ""
    },
    "source_summary": {
      "files": 0,
      "lines": 0,
      "tables": 0
    }
  },
  "actors": [
    {
      "id": "",
      "name": "",
      "description": "",
      "category": "person|system",
      "actions": [
        {
          "area_id": "",
          "action": "",
          "description": ""
        }
      ]
    }
  ],
  "areas": [
    {
      "id": "",
      "name": "",
      "one_liner": "",
      "purpose": "",
      "parent_area_id": null,
      "child_area_ids": [],
      "related_area_ids": [],
      "actors": [
        {
          "actor_id": "",
          "actions": []
        }
      ],
      "concepts": [],
      "concept_crud": [
        { "concept_id": "", "ops": "CRUD" }
      ],
      "overview_flow": {
        "title": "",
        "lanes": [ "<actor_id>" ],
        "steps": [ { "lane": "<actor_id>", "label": "", "use_case": "" } ]
      },
      "flows": [],
      "apis": [],
      "screens": [],
      "code_refs": [],
      "risk_points": [],
      "open_questions": [],
      "confidence": "high|medium|low"
    }
  ],
  "concepts": [
    {
      "id": "",
      "name": "",
      "description": "",
      "kind": "entity|state|event|value_object|external_system|screen|api",
      "physical_tables": [],
      "tags": [],
      "crud_by_area": [
        { "area_id": "", "ops": "CRUD" }
      ],
      "related_areas": [],
      "states": [],
      "code_refs": [],
      "confidence": "high|medium|low"
    }
  ],
  "classifications": [
    {
      "id": "",
      "name": "",
      "description": "",
      "concept_id": null,
      "values": [ { "code": "", "label": "" } ],
      "code_refs": [],
      "confidence": "high|medium|low"
    }
  ],
  "components": [
    {
      "id": "",
      "name": "",
      "description": "",
      "kind": "infrastructure|middleware|external",
      "code_refs": [],
      "confidence": "high|medium|low"
    }
  ],
  "flows": [
    {
      "id": "",
      "name": "",
      "description": "",
      "area_id": "",
      "actor_ids": [],
      "steps": [],
      "affected_concepts": [],
      "crud": {},
      "confidence": "high|medium|low"
    }
  ],
  "validations": []
}
```

### 概念データとCRUDのモデル（重要）

* **物理テーブル**（実際のDBテーブルやORMモデル）は、業務的意味でまとめた**概念データ**に
  圧縮する。概念には `physical_tables` で根拠となる物理テーブル名を持たせる。
* **CRUDの正本は概念データ側**に置く。各領域は自分が触る概念について
  `concept_crud: [{concept_id, ops}]` を宣言するだけにする（ops は "C"/"R"/"U"/"D" の部分集合）。
* `merge` が各領域の `concept_crud` を集約し、概念側に
  `crud_by_area: [{area_id, ops}]` と `related_areas` を生成する。CRUDビューは
  この同一データを1つの並び替え・絞り込み可能な表として表示する。
* 旧 `crud_summary` / 領域側 `tables` フィールドは廃止（CRUDは概念単位、テーブルは
  概念の `physical_tables` に集約）。

### 概念データの任意タグ（システム固有）

* 重要度や区別はシステムごとに異なる（例: あるシステムでは「マスタ／トランザクション」の
  区別が重要）。そこで概念には自由な `tags: []`（文字列）を持たせる。
* タグ語彙はシステム固有なので、プロジェクトごとに `.dramaturgy/tags.json` で管理する。
  各タグは**意味（description）**を持ち、**グループ（group）**に属させられる。グループは
  `groups: [{name, description}]`、タグは `tags: [{name, description, group}]`。語彙は
  **助言的**で、サジェスト・凡例・Claudeへの提示に使うが、概念に任意のタグ文字列を付けてよい。
* 付与は2経路: ① カード生成時に Claude がシステム固有観点で付与（語彙＝グループ・意味込みを渡す）、
  ② 人間が UI で直接編集（Claude不要の軽量操作として `PATCH /api/concept/<id>` で
  `meaning-map.json` に書き戻す）。語彙自体は `GET/PUT /api/tags` で編集する。
* HTMLでは概念データ表にタグ列を設け、タグでの絞り込みを可能にする。タグの意味は
  ツールチップで、グループ別の凡例も表示する。

### 区分（classifications）と概念データの区別

* 「ポイント付与方法」「メール種別」「取消コード」のような**取りうる値の集合**は、概念データ
  （エンティティ）ではなく**区分**として `classifications[]` に切り出す。概念データに全値を
  並べると膨大になるため。
* 各区分は `values: [{code, label}]` を持つ。`concept_id` があれば「その概念を展開した詳細」、
  null なら「業務ロジックの前提となる単独の区分」として扱う。
* HTMLでは区分を独立セクションに表示し、概念ごと／前提区分に分けて見せる。

### 登場人物（actors）と構成（components）の区別

* actors には `category` を付ける。`person`=業務上の登場人物（厳密には人でなくても業務フロー上
  アクター扱いが自然なものを含む）、`system`=アクター扱いする外部システム・端末（決済代行・
  外部会員システム・入場ゲート端末など）。
* ロードバランサ・監視基盤・横断ミドルウェアのような**業務上の登場人物ではない構成要素**は
  actors に入れず `components[]` に分離する。
* HTMLでは actors を category でグループ表示し、components は別セクションにする。
* これらはレビュー対象でもある（`target_type` に classification / component を追加）。

## Claude用プロンプト

以下に示すのは `content_lang: ja` のテンプレートである。各プロンプトは言語別テンプレートとして管理し、`en` 版を同等の指示密度で用意する。いずれの言語でも、生成物の自然言語フィールドは `content_lang` で記述するよう明示する。

## Claude用プロンプト: 領域ツリー作成 (ja)

```text
あなたは大規模業務システムの意味地図を作る分析者です。

あなたは Claude Code として、対象リポジトリのファイルを直接読めます。与えられるのは
ファイル/ディレクトリの目録のみです。実際の業務領域・概念・エンティティは、あなたが
ソースコード（モデル/マイグレーション/ルーティング等）を読んで発見してください。

最重要方針:
- ファイル数やトークン数ではなく、業務・概念・責務の自然さを最優先してください
- 利用者、管理者、運用者、システムが何をするかが自然に説明できる単位で分けてください
- テーブルやエンティティは SQL とは限りません。ORM・マイグレーション・規約で定義され得るので
  該当ファイルを開いて確認してください
- テーブル名やディレクトリ名をそのまま領域名にしないでください
- 1領域が大きすぎると判断した場合のみ、自然な子領域に分けてください
- 意味的に切れないものを、分量だけで無理に分けないでください
- 不明点は confidence: low としてください
- 自然言語フィールド(name, one_liner, purpose など)は日本語で書いてください
- 出力JSONの先頭に "content_lang": "ja" を含めてください

出力は area-tree.json のJSONのみとしてください。
```

## Claude用プロンプト: 領域カード生成 (ja)

```text
あなたは既存業務システムの意味地図を作る分析者です。

以下は、すでに人間に自然な業務・概念単位として切り出された領域です。

この領域について、利用者にも開発者にも理解しやすい領域カードを生成してください。

目的は詳細仕様書を書くことではありません。
人間が短時間でこの領域の意味を理解でき、必要に応じてコード・DB・APIに降りられるようにしてください。

必ず以下を整理してください。

- 領域名
- 一言説明
- 目的
- 登場人物ごとの行動
- 主要概念
- 主要フロー
- CRUD要約
- 関連DBテーブル
- 関連API
- 関連画面
- 関連コード
- 状態遷移
- 注意点
- open_questions
- confidence

注意:
- 実装詳細を本文に詰め込みすぎないでください
- ただし、根拠となるコード・DB・APIへの参照は残してください
- 推測と根拠を分けてください
- 自然言語フィールドは日本語で書き、"content_lang": "ja" を含めてください
- JSONのみで出力してください
```

## Claude用プロンプト: 分割妥当性レビュー (ja)

```text
あなたは大規模業務システムの領域分割をレビューする設計者です。

以下の area-tree.json が、人間が見て自然な分割になっているか確認してください。

観点:
- 業務担当者が理解しやすい領域名か
- 登場人物ごとの行動が自然に説明できるか
- 1領域が複数の責務を持ちすぎていないか
- 逆に、分けすぎて理解しづらくなっていないか
- 親子領域の関係が自然か
- 関連領域と親子領域が混同されていないか
- DBテーブルやディレクトリ構造に引っ張られすぎていないか
- 分量が多すぎる場合、自然な細分化案があるか

出力:
{
  "verdict": "OK|WARN|NG",
  "good_points": [],
  "unnatural_splits": [],
  "missing_areas": [],
  "over_split_areas": [],
  "under_split_areas": [],
  "suggested_tree_changes": [],
  "notes": []
}
```

## 重要な運用ルール

* 正本は meaning-map.json と area-tree.json
* HTMLは生成物（ビュー）であり、Web UI上の編集は正本JSONへ書き戻す
* 実行はユーザーが手でスクリプトを叩くのではなく、Web UI または Claude Code のカスタムコマンドから行う
* Web UIは Claude Code をヘッドレス起動して意味判断を実行させ、結果を正本JSONへ書かせる
* サーバは 127.0.0.1 のみにバインドする（ローカル単一利用者向け）
* スクリプト（CLI）は「信頼できる事実（ファイル/ディレクトリ目録）」の収集と機械検査のみを担当する
* テーブル・エンティティ・API・ルート等の意味的事実は機械抽出せず、Claudeがソースを読んで発見する
* Claudeは意味判断を担当する
* Claude をヘッドレス起動するジョブは、一時的なAPIエラーを指数バックオフでリトライする
* 一括初期化では、ある領域カードが失敗してもパイプライン全体を止めず、スキップして最後に報告する（部分的な地図を残し、後から個別再生成できる）
* 実行中はジョブの経過時間・プロセスID・CPU/メモリ使用量をUIに表示し、セッションが生きていることを可視化する
* 領域分割は必ずClaudeが一度レビューする
* 領域の階層（parent/child/related）の正本は area-tree.json。領域カード生成では階層を発明させず、
  ツリーの値をそのままコピーさせる（パックにツリーの parent/child/related を含めて渡す）。
* 一括初期化では merge 後に、親子関係（parent_area_id / child_area_ids）を area-tree.json から
  meaning-map.json へ上書きする。階層の正本はツリーなので、カードが階層を省いても子領域レビューの
  分割結果が地図に反映される（ツリーに無い領域は触らない）。
* merge は防御として、実在しない領域IDへの parent/child/related 参照を除去し、
  merge_report.dropped_area_refs に記録する（未定義参照を地図に残さない）。
* 分量超過は「自動分割」ではなく「自然な下位領域案」として扱う
* confidence が low の箇所はHTML上で明示する
* 人間が修正しやすいJSONを中間成果物として残す
* Git差分でレビューしやすいように、整形済みJSONを出力する
* 言語設定 (ui_lang / content_lang) は config.json を正本とし、各CLIは引数で上書きできる
* UI/CLI文言とプロンプトはコードに直書きせず、言語別カタログ／テンプレートに分離する
* 1つの正本JSONは単一 content_lang。別言語が必要なら content_lang を変えて再生成する
* 公開リポジトリには日本語・英語の README を用意し、対応言語の追加手順を明記する

