# pipeline 输出契约

`python scripts/kg_engine.py pipeline input.json` 返回如下结构（UTF-8 JSON）：

```
{
  "case_id": str,
  "status": "ok" | "needs_attention",
  "result": {
    "entity_extraction": {
      "checked": int, "accepted": int, "rejected": int,
      "entities": [entity_report], "rejected_ids": [str]
    },
    "relation_check": {
      "checked": int, "accepted": int, "rejected": int,
      "relations": [relation_report], "rejected_ids": [str]
    },
    "entity_alignment": {
      "merge_count": int, "conflict_count": int,
      "merges": [{canonical, basis, member_ids, sources}],
      "conflicts": [{key, reason, surfaces, sources, decision, ...}],
      "canonical_of": {entity_id: canonical},
      "node_count_after": int
    },
    "source_bindings": [binding_report],
    "graph_query": {
      "query_count": int, "answered": int, "min_three_queries": bool,
      "all_traceable": bool, "answers": [answer]
    },
    "export_check": {...},
    "incremental_update": {...} | null,
    "graph": {"nodes": [...], "edges": [...]}
  },
  "evidence": {
    "principles": {"抽得准","连得对","对得齐","查得到回得去"},
    "rejected_entities": [str], "rejected_relations": [str],
    "cross_paper_conflicts": [...], "unbound_items": [str]
  },
  "uncertainty": {
    "needs_review": [...],
    "note": "价值判断须 Agent 结合原文复核；不臆造；位置为 JATS 段落ID"
  }
}
```

## entity_report

`id, surface, type, type_zh, source_id, paragraph_id, quote, attribution, grounded, quote_in_source, entity_ok, issues[]`

`issues[].type`：bad_entity_type / empty_surface / no_source_id / unknown_source_id / no_anchor / fake_pdf_page / bad_anchor_format / no_quote / not_grounded(warning) / quote_mismatch(warning) / bad_attribution

## relation_report

`id, subject, relation, object, direction, condition, evidence_type, quote, source_id, paragraph_id, cross_paper, relation_ok, issues[]`

`issues[].type`：bad_relation_type / missing_endpoint / self_loop / weak_evidence_as_relation(error) / bad_evidence_type / no_quote / bad_anchor / fake_pdf_page / no_condition(warning) / dangling_endpoint / cross_paper_unmarked(error) / cross_paper_weak_evidence(error) / bad_direction

## binding_report

`id, bound, quote_in_source, source_id, paragraph_id, quote, issues[]`

## answer

`query_id, query_type, query, matched_nodes[], matched_edges[], subgraph{nodes,edges}, evidence[{kind,id,source_id,paragraph_id,quote,quote_in_source?}], traceable, unresolved_edges[], has_answer`

## status 判定

`ok` 需同时满足：无被拒实体、无被拒关系、所有有答案的查询 traceable、导出 machine_readable、所有节点与边 bound。否则 `needs_attention`，并在 `evidence` / `uncertainty` 列出待复核项。


## 端到端交付（完成器 solve / render-draft）

### 真实输入字段（solve 适配）

`solve case.json --out /app/output` 读取 case.json，支持以下真实输入字段（读不到不臆造，记入 `adapter_notes`）：

- `source_index`：`{论文ID: {JATS段落ID: 原文}}`（内联），或 `source_files`（`{名:路径}`，读 `.json` 索引或 `.txt` 文本）。
- `entities` / `entities_file`、`relations` / `relations_file`、`queries` / `queries_file`：内联或真实 JSON 文件。
- `extract_from_text`（默认 true）：**无预填 entities 时从正文驱动抽取候选实体**——受控词表正则，带 source_id/JATS paragraph_id/quote/attribution，真伪仍经 check_entity 校验，不臆造。
- `alias_rules`、`export_format`、`incremental`：别名规则、导出格式与可选增量更新。

### 输出：solve result.json

```json
{
  "case_id": "...",
  "status": "ok | needs_attention | partial",
  "input_mode": "case",
  "source_count": 2,
  "adapter_notes": ["正文抽取候选:19"],
  "result": {
    "draft_text": "# 知识图谱交付稿（可编辑）\n## 节点（4）\n- CNN [method]（P1/sec2.p3...）\n## 关系（2）\n...",
    "nodes": [{"surface":"CNN","type":"method","source_id":"P1","paragraph_id":"sec2.p3","quote":"CNN方法"}],
    "edges": [{"subject":"...","relation":"uses","object":"...","source_id":"P1","paragraph_id":"sec4.p2"}],
    "node_count": 4, "edge_count": 2,
    "entity_extraction": {...}, "relation_check": {...}, "entity_alignment": {...},
    "graph_query": {...}, "export_check": {...},
    "summary": "节点 4；关系 2；实体拒收 0；关系拒收 0；查询 3/3 可回链；导出合规"
  },
  "needs_review": [...],
  "uncertainty": ["节点/边只取真实实体/关系（经校验）；无实体标〔待补〕，不臆造..."],
  "delivery": {"written":true,"path":"/app/output/result.json","bytes":11735}
}
```

- `result.draft_text`：可编辑知识图谱交付稿：校验通过的节点/边（带来源绑定）+ 导出合规结论；**无实体标〔待补：无通过校验的实体〕，不臆造实体、关系或证据**。
- `result.nodes` / `edges`：经 check_entity/check_relation 校验通过的图结构，每个节点带 source_id/JATS paragraph_id/quote；位置为 JATS 段落 ID 而非 PDF 页码。
- `adapter_notes` 含「正文抽取候选:N」表示无预填时走了正文驱动抽取路径。
- `status`：`ok`=无拒收实体/关系 + 查询可回链 + 导出合规 + 全部绑定；否则 `needs_attention`/`partial`。
- `delivery`：落盘回执；`written=true` 且 `bytes>0` 才算交付成功。异常不静默吞错，写入 `input_error` 或显式降级。

### render-draft / pipeline --with-draft

`render-draft input.json` 与 `pipeline input.json --with-draft` 在输出中给出 `draft_detail`（含 `draft_text`/`nodes`/`edges`/`needs_author_confirmation`）；默认 `pipeline` 不含成稿。两者都不臆造实体/关系/证据，缺口标〔待补〕。
