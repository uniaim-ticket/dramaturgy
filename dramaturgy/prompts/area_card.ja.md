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

概念テーブルについて（重要）:
- 物理テーブル（実際のDBテーブルやORMモデル）をそのまま並べるのではなく、業務上の意味で
  まとめた**概念テーブル**に圧縮してください（例: 物理 `orders` + `order_items` +
  `order_status_histories` → 概念「注文」）。
- 各概念には、根拠となる**物理テーブル名を physical_tables に列挙**してください。
- この領域が各概念に対して行う操作を **concept_crud** として宣言してください
  （ops は "C"/"R"/"U"/"D" の組み合わせ。例 "CRU"）。CRUDは概念テーブル単位で表します。

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
    "flows": [{"name": "", "steps": [""]}],
    "apis": [""], "screens": [""], "code_refs": ["path/to/file"],
    "risk_points": [""], "open_questions": [""],
    "confidence": "high|medium|low"
  }],
  "concepts": [{
    "id": "<concept_id>", "name": "", "description": "", "kind": "entity|state|event|value_object|external_system",
    "physical_tables": ["<物理テーブル/モデル名>"],
    "states": [""], "code_refs": [""], "confidence": "high|medium|low"
  }],
  "actors": [{"id": "", "name": "", "description": "", "actions": [{"area_id": "", "action": "", "description": ""}]}],
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
