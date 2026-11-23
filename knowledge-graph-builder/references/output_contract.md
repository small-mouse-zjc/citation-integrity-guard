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
    "coverage_check": {
      "ok": bool, "issues": [...], "entity_count": int, "edge_count": int,
      "entity_types": [str], "relation_types": [str],
      "query_total": int, "query_answered": int, "query_traceable": int
    },
    "incremental_update": {...} | null,
    "graph": {"nodes": [...], "edges": [...]},
    "artifacts": {"graph_json": "...", "query_answers_json": "...", "coverage_json": "...", "outdir": "..."}
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

`ok` 需同时满足：无被拒实体、无被拒关系、所有有答案的查询 traceable、导出 machine_readable、所有节点与边 bound、`coverage_check.ok=true`（至少 3 个查询、图谱不小于 2 节点/1 边）。否则 `needs_attention`，并在 `evidence` / `uncertainty` 列出待复核项。
