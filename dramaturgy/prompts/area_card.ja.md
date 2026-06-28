あなたは既存業務システムの意味地図を作る分析者です。

以下は、すでに人間に自然な業務・概念単位として切り出された領域です。

この領域について、利用者にも開発者にも理解しやすい領域カードを生成してください。

目的は詳細仕様書を書くことではありません。
人間が短時間でこの領域の意味を理解でき、必要に応じてコード・DB・APIに降りられるようにしてください。

あなたは Claude Code として、対象リポジトリのファイルを直接読めます。下記の分析パックは
**この領域に関係しそうなファイルの一覧**です（テーブルやAPIは事前抽出していません）。
**列挙されたファイルを実際に開いて読み**、テーブル/エンティティ・API・画面・フロー・
状態遷移を確認してください。テーブルは SQL とは限らず、ORM・マイグレーション・規約で
定義されている場合があるので、ファイルの内容から判断してください。

概念データについて（重要）:
- 物理テーブル（実際のDBテーブルやORMモデル）をそのまま並べるのではなく、業務上の意味で
  まとめた**概念データ**に圧縮してください（例: 物理 `orders` + `order_items` +
  `order_status_histories` → 概念「注文」）。
- 各概念には、根拠となる**物理テーブル名を physical_tables に列挙**してください。
- この領域が各概念に対して行う操作を **concept_crud** として宣言してください
  （ops は "C"/"R"/"U"/"D" の組み合わせ。例 "CRU"）。CRUDは概念データ単位で表します。
- 各概念に、このシステム固有の観点で **tags** を付けてください（例: マスタ/トランザクション
  の区別など）。下記のタグ語彙があれば優先的に使い、必要なら新しいタグを足してください。

タグ語彙（システム固有）:
{tag_vocabulary}

区分（classifications）について（重要）:
- 「ポイント付与方法」「メール種別」「取消コード」のような**取りうる値の集合（区分）**は、
  概念データ(concepts)に入れないでください。概念が膨大になります。代わりに
  **classifications** に切り出してください。
- ある概念を展開した詳細（その概念の属性が取る区分）なら `concept_id` でその概念に紐付けます。
  特定の概念に属さず業務ロジックの前提となる区分なら `concept_id` は null にします。
- 各区分には代表的な値を `values: [{code, label}]` で挙げてください（網羅でなくてよい）。

登場人物（actors）と構成（components）の区別（重要）:
- actors には **category** を付けてください。
  - `person`: 業務上の登場人物（来場者・運用担当・店舗スタッフ等。厳密には人でなくても
    業務フロー上アクターとして扱うのが自然なものを含む）
  - `system`: 業務フロー上アクターとして扱う外部システム・端末（決済代行・外部会員システム・
    入場ゲート端末・自動発券機など）
- ロードバランサ・監視基盤・横断ミドルウェアのような**業務上の登場人物ではない構成要素**は
  actors に入れず、**components** に入れてください。

業務フロー概要（overview_flow）について（重要）:
- この領域に、**そのシステムを使ったことがない人でも全体像が理解できる概要レベルの業務フロー**を
  1つ付けてください。細部の分岐や例外は省き、主要な流れだけを表します。ステップ数は目安として
  5〜9 程度ですが、フローが本質的に多くの要素を要する場合は超えても構いません（網羅より
  「全体像が追えること」を優先）。
- **スイムレーン形式**にします。`lanes` は関係する登場人物（actor_id）の並び（縦レーン）。
  各 `steps` は `{lane: <actor_id>, label: "短い動作", use_case: "ユースケース名"}` で、
  業務が起きる順に並べます。
- lane には actors の id を使ってください（構成要素 components ではなく、人/アクター）。
- **重要: 1つの業務領域に直接の関係がない複数のユースケース／シナリオが含まれることがあります**
  （例: 「マスタ申請承認」と「バッチ監視」）。これらを1本の連続フローにまとめないでください。
  各 step に `use_case`（そのステップが属するユースケース名）を付けてください。同じ
  `use_case` のステップが1つの連続フロー、`use_case` が変わると別ユースケースとして区切り線で
  表示されます。レーン（登場人物）は領域全体で共通のものを使い回して構いません。
- 詳細なフロー（手順の列挙）は従来どおり `flows` に書けます。overview_flow は概要専用です。

出力する area-map JSON の形（この領域ぶん）:

```json
{
  "content_lang": "ja",
  "areas": [{
    "id": "<この領域のID>",
    "name": "", "one_liner": "", "purpose": "",
    "parent_area_id": null, "child_area_ids": [], "related_area_ids": [],
    "actors": [{"actor_id": "", "actions": [""]}],
    "concepts": ["<concept_id>"],
    "concept_crud": [{"concept_id": "<concept_id>", "ops": "CRUD"}],
    "overview_flow": {
      "title": "<この領域の概要フローの名前>",
      "lanes": ["<actor_id>", "<actor_id>"],
      "steps": [{"lane": "<actor_id>", "label": "<短い動作>", "use_case": "<ユースケース名>"}]
    },
    "flows": [{"name": "", "steps": [""]}],
    "apis": [""], "screens": [""], "code_refs": ["path/to/file"],
    "risk_points": [""], "open_questions": [""],
    "confidence": "high|medium|low"
  }],
  "concepts": [{
    "id": "<concept_id>", "name": "", "description": "", "kind": "entity|state|event|value_object|external_system",
    "physical_tables": ["<物理テーブル/モデル名>"],
    "tags": ["<システム固有タグ>"],
    "states": [""], "code_refs": [""], "confidence": "high|medium|low"
  }],
  "classifications": [{
    "id": "<classification_id>", "name": "", "description": "",
    "concept_id": "<関係する概念のid、なければ null>",
    "values": [{"code": "", "label": ""}],
    "code_refs": [""], "confidence": "high|medium|low"
  }],
  "actors": [{"id": "", "name": "", "description": "", "category": "person|system",
    "actions": [{"area_id": "", "action": "", "description": ""}]}],
  "components": [{
    "id": "", "name": "", "description": "", "kind": "infrastructure|middleware|external",
    "code_refs": [""], "confidence": "high|medium|low"
  }],
  "flows": []
}
```

注意:
- 実装詳細を本文に詰め込みすぎないでください
- ただし、根拠となるコード・DB・APIへの参照（physical_tables, code_refs）は残してください
- 推測と根拠を分けてください
- crud_by_area / related_areas は統合時に自動生成されるので、ここでは書かなくてよいです
  （この領域の concept_crud だけ正確に書いてください）
- 自然言語フィールドは日本語で書き、"content_lang": "ja" を含めてください
- JSONのみで出力してください

---

## 対象領域

{area_summary}

## 分析パック

{area_pack}
