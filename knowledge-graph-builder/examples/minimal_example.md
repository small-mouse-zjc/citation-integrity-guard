# 最小可运行示例

> 说明：以下输入/输出仅用于说明接口，文本为最小自造样本，**不是**正式评测案例答案。正式运行请用平台给的真实论文原文。

## 输入 input.json

```json
{
  "case_id": "MINI-01",
  "source_index": {
    "P1": {"sec2.p3": "本文提出CNN方法在碳酸盐岩薄片上达到0.92准确率。"},
    "P2": {"sec1.p2": "我们报告CNN方法在页岩样本上取得0.85的F1值。"}
  },
  "known_papers": ["P1", "P2"],
  "entities": [
    {"id": "n1", "surface": "CNN", "type": "method", "source_id": "P1", "paragraph_id": "sec2.p3", "quote": "CNN方法", "attribution": "self"},
    {"id": "n2", "surface": "CNN", "type": "method", "source_id": "P2", "paragraph_id": "sec1.p2", "quote": "CNN方法", "attribution": "self"}
  ],
  "relations": [],
  "queries": [
    {"id": "Q1", "type": "entity", "surface": "CNN"},
    {"id": "Q2", "type": "entity", "surface": "不存在"},
    {"id": "Q3", "type": "relation", "relation": "uses"}
  ]
}
```

## 运行

```bash
python scripts/kg_engine.py pipeline input.json > result.json
```

## 关键点

- 两个 surface 都是 "CNN" 但 source_id 不同（P1/P2），引擎在 `entity_alignment.conflicts` 里给出 `cross_paper_same_surface`，保留为两个节点——不会因为名字相同就合并成一个。
- Q2 查不到的对象：`has_answer=false`，如实返回空，不拿共现凑数。
- 每个节点位置用 `sec2.p3` 这样的 JATS 段落 ID，不是"第1页"。

## 输出（节选）

```json
{
  "status": "needs_attention",
  "result": {
    "entity_alignment": {
      "conflicts": [{
        "reason": "cross_paper_same_surface",
        "surfaces": ["CNN", "CNN"],
        "sources": ["P1", "P2"],
        "decision": "kept_separate"
      }]
    },
    "graph_query": {
      "answers": [
        {"query_id": "Q1", "has_answer": true, "traceable": true},
        {"query_id": "Q2", "has_answer": false},
        {"query_id": "Q3", "has_answer": false}
      ]
    }
  },
  "evidence": {"cross_paper_conflicts": [{"reason": "cross_paper_same_surface"}]}
}
```

`status=needs_attention` 是因为弱项（跨篇冲突、无结果查询）被如实标注，属正常诚实输出，不代表运行失败。
