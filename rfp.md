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

`dra serve` でローカルWebサーバ（`127.0.0.1` のみ）を起動し、ブラウザUIで意味地図を閲覧・編集する。requirements-reviewer (rr) と同じ考え方で、HTML/JSON成果物を中心に据える。

* 重い意味判断（領域ツリー生成・領域カード生成）は、UIのボタンから **Claude Code をヘッドレス起動**して実行する:
  `claude -p "<prompt>" --output-format stream-json --permission-mode acceptEdits --add-dir <repo>`
* `acceptEdits` を既定にするのは、ヘッドレス実行では対話的な許可応答ができないため。Claude がワークスペース内のJSONを直接書き込めるようにする。
* 進捗は stream-json をパースし、UIは**ポーリング**で表示する（バッファリングするプロキシでも止まらないため）。
* セッションIDを保持し、追撃の指示は `--resume` で文脈を引き継ぐ。

### 方式B: Claude Code のカスタムコマンド

解析対象リポジトリ上の Claude Code セッションで、同梱のカスタムコマンドを使う。

```text
/dramaturgy:analyze    リポジトリ索引（dra analyze-* + candidates）
/dramaturgy:tree       Claude が area-tree.json を作成
/dramaturgy:cards [id] Claude が area-maps/<id>.json を作成
/dramaturgy:finalize   merge + validate + render
```

### 書き戻し（双方向）

* 正本は `area-tree.json` / `meaning-map.json`。HTMLは生成ビュー。
* Claude Code は意味判断の結果を正本JSONへ直接書き込む。
* Web UI 上の人間の編集（領域名・一言説明・注意点など）は、API経由で正本JSONへ**書き戻す**（`PUT /api/artifact/<name>`、`PATCH /api/area/<id>`）。生JSON編集と構造化フィールド編集の両方を許す。
* どちらの経路で編集しても、HTMLは正本JSONから再描画される。

## Claude Code 内での使い方

Claude Code は以下のように進める。

```text
0. セットアップ: ui_lang / content_lang / project を設定し config.json を作る
1. リポジトリ全体のインデックスを作成する
2. DBスキーマ・API・画面・モデル候補を抽出する
3. Claude が自然な業務領域案を作る
4. CLI が分量・参照関係・不足情報を補助的に計測する
5. Claude が領域ツリーを調整する
6. 各領域について意味地図カードを生成する
7. 別観点でClaudeが検証する
8. JSONを統合する
9. HTMLを生成する
```

ステップ0以降のCLIは、引数で言語を明示しない限り config.json の `ui_lang` / `content_lang` を既定値として使う。

## CLIツールの役割

CLIツールは、意味判断を主導しない。

CLIツールは、Claude が意味判断しやすくするための材料を集める。

必要なCLIは以下。すべてのCLIは共通で `--ui-lang {ja|en}` を受け取り、進捗・警告・エラーをその言語で出力する。生成系CLIはさらに `--content-lang {ja|en}` を受け取る。いずれも省略時は config.json の値を使う。

### コマンド体系

ツール名は `dramaturgy`、短縮コマンドは `dra`（両者は同一CLIに解決する）。各機能は個別スクリプトではなく `dra <サブコマンド>` として提供する。`dra --help` で一覧、`dra <サブコマンド> --help` で個別オプションを表示する。以下の各節は機能単位で、見出しの括弧内が対応するサブコマンド名である。

```text
setup           初期セットアップ（config.json 生成）
analyze-repo    ソース索引
analyze-schema  DBスキーマ索引
candidates      領域候補材料
tree-prompt     領域ツリープロンプト生成
pack            領域分析パック生成
subdivide       子領域案の提示
merge           領域マップ統合
validate        機械的整合性＋言語不変条件の検査
render          HTML生成
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

* ソースコードの索引を作る
* ファイル数・行数・拡張子・ディレクトリを集計する
* 主要なコード候補を抽出する

出力:

```text
.dramaturgy/source-index.json
```

抽出するもの:

* ファイル一覧
* 行数
* import / require / use
* class / function / method 名
* route 候補
* controller 候補
* model 候補
* migration 候補
* view / screen 候補
* batch / job / command 候補
* table name 候補

### 2. analyze-schema（`dra analyze-schema`）

目的:

* DBスキーマから概念候補を出す

出力:

```text
.dramaturgy/schema-index.json
```

抽出するもの:

* テーブル
* カラム
* 外部キー
* enum/status系カラム
* 履歴テーブル候補
* 中間テーブル候補
* マスタテーブル候補
* 集計テーブル候補

### 3. candidates（`dra candidates`）

目的:

Claude が領域分割しやすいように、候補材料を出す。

注意:

このツールの出力は最終判断ではない。

出力するもの:

* ディレクトリ別まとまり
* テーブル関係グラフ
* API prefix 別まとまり
* モデル参照関係
* 画面/Controller/Route のまとまり
* status カラムごとのライフサイクル候補
* ファイル量の多い候補領域

出力:

```text
.dramaturgy/area-candidates.json
```

### 4. tree-prompt（`dra tree-prompt`）

目的:

Claude に自然な領域ツリーを作らせるためのプロンプト材料を生成する。

入力:

* source-index.json
* schema-index.json
* area-candidates.json

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

### 5. pack（`dra pack`）

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
  --schema-index .dramaturgy/schema-index.json \
  --out .dramaturgy/area-packs/ticket_sales.application.md
```

役割:

* area-tree で指定された領域に関係するファイルを集める
* 関連テーブルを集める
* 関連APIを集める
* 関連画面を集める
* トークン数を見積もる
* 大きすぎる場合は警告する
* ただし勝手に分割しない

### 6. subdivide（`dra subdivide`）

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

### 7. merge（`dra merge`）

目的:

領域ごとの meaning map を統合する。

役割:

* area-map JSON を統合する
* ID重複検出
* 概念名の揺れ検出
* 関連領域リンク補完
* 親子関係の整合性検査
* 孤立領域の検出

### 8. render（`dra render`）

目的:

meaning-map.json からHTMLを生成する。

HTMLに必要なビュー:

* 全体地図
* 業務領域カード
* 登場人物ビュー
* 概念ビュー
* CRUDマトリクス
* 開発者向け参照ビュー
* 検証結果ビュー

言語の扱い:

* ラベル・ナビゲーション・見出しなどの固定文言(chrome)は `ui_lang` のメッセージカタログから差し込む。
* 本文コンテンツ（領域名・説明・概念など）は meaning-map.json の `content_lang` のまま表示する。
* HTMLには `<html lang="...">` に content_lang を反映し、chromeとコンテンツの言語が異なる場合もある旨を考慮する。

### 9. validate（`dra validate`）

目的:

機械的に検査できる整合性を確認する。

検査内容:

* 参照先ファイルが存在するか
* テーブル名が schema-index に存在するか
* API名が source-index に存在するか
* CRUD対象が concepts に存在するか
* parent_area_id / child_area_ids が一致しているか
* related_area_ids が存在するか
* 循環参照がないか
* confidence: low の項目が一覧化されているか
* config.json の `ui_lang` / `content_lang` が対応言語か
* meaning-map.json / area-tree.json に `content_lang` が記録され、config と一致するか
* UI/CLIメッセージカタログに全対応言語ぶんのキーが揃っているか（欠落キーの一覧化）

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
    "generated_at": "",
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
      "flows": [],
      "crud_summary": {},
      "tables": [],
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
      "related_tables": [],
      "related_areas": [],
      "states": [],
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

## Claude用プロンプト

以下に示すのは `content_lang: ja` のテンプレートである。各プロンプトは言語別テンプレートとして管理し、`en` 版を同等の指示密度で用意する。いずれの言語でも、生成物の自然言語フィールドは `content_lang` で記述するよう明示する。

## Claude用プロンプト: 領域ツリー作成 (ja)

```text
あなたは大規模業務システムの意味地図を作る分析者です。

以下のリポジトリ索引、DBスキーマ索引、領域候補材料をもとに、人間が見て自然な業務領域ツリーを作ってください。

最重要方針:
- ファイル数やトークン数ではなく、業務・概念・責務の自然さを最優先してください
- 利用者、管理者、運用者、システムが何をするかが自然に説明できる単位で分けてください
- DBテーブル名をそのまま領域名にしないでください
- 300テーブルをそのまま並べず、概念Entityに圧縮してください
- 1領域が大きすぎると推測される場合のみ、自然な子領域に分けてください
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
* スクリプト（CLI）は材料集めと機械検査を担当する
* Claudeは意味判断を担当する
* 領域分割は必ずClaudeが一度レビューする
* 分量超過は「自動分割」ではなく「自然な下位領域案」として扱う
* confidence が low の箇所はHTML上で明示する
* 人間が修正しやすいJSONを中間成果物として残す
* Git差分でレビューしやすいように、整形済みJSONを出力する
* 言語設定 (ui_lang / content_lang) は config.json を正本とし、各CLIは引数で上書きできる
* UI/CLI文言とプロンプトはコードに直書きせず、言語別カタログ／テンプレートに分離する
* 1つの正本JSONは単一 content_lang。別言語が必要なら content_lang を変えて再生成する
* 公開リポジトリには日本語・英語の README を用意し、対応言語の追加手順を明記する

