---
name: knowledge-graph-builder
description: 文献知识图谱构建守门人。当任务要求从科研论文抽取实体（研究者/材料/方法/任务/指标/结论/模型/数据集）、建立有证据支持的关系、处理别名缩写与同名冲突、为节点和边绑定原文位置证据、执行图谱查询或增量加入新论文并保持既有编号时使用本技能。通过确定性脚本把抽得准、连得对、对得齐、查得到回得去四件事落成可复核的图谱结构，坚持跨篇同表面不强并、共现与推测不作直接证据、位置用JATS段落ID而非自造页码，不臆造实体、关系、证据或来源。不适用于纯翻译润色或非文献的通用知识图谱。
---

# 文献知识图谱构建守门人（Knowledge Graph Builder）

面向两篇及以上真实论文的知识图谱 skill。目标不是"把实体词表堆成节点"，而是让每个实体**真在论文出现**、每条关系**有直接证据与方向条件**、每处别名合并**有依据且跨篇不误并**、每个查询结果**能回到论文的 JATS 段落与原文短引**。

## 四个核心问题

| 核心问题 | 含义 | 对应子命令 |
|---------|------|-----------|
| 抽得准 | 实体对应论文真实出现的科研对象，类型合法，保留原文位置与表述，区分作者自述/他人转述 | `extract-entities` |
| 连得对 | 关系类型、方向与适用条件与原文一致，不把共现、综述转述、推测当直接证据 | `check-relations` |
| 对得齐 | 别名/缩写/大小写/同名冲突正确处理，既不重复节点也不跨篇错误合并 | `align-entities` |
| 查得到、回得去 | 图谱能回答真实查询，每个节点与边都能回到论文段落位置与原文片段 | `query-graph` |

另有 `bind-source`（逐节点/边核验来源绑定）、`incremental-update`（增量加入新论文保留编号）、`check-export`（导出合规），`pipeline` 一次跑完全流程；`pipeline.result.coverage_check` 检查图谱完整度与至少 3 个可答查询。

## 何时触发 / 何时不触发

**触发**：从论文批量抽取实体关系、构建可查询图谱、处理别名与同名冲突、为知识单元绑定原文证据、增量并入新论文、按主题做文献知识结构化。

**不触发**：纯翻译/润色、非科研文本的信息抽取。被误触发时说明并保持原文不变。

## 六条铁律（贯穿所有动作）

1. **抽得准**：实体表面形式必须能在指定论文的指定 JATS 段落原文中命中；命中不了标 `not_grounded`，绝不凭常识补全。
2. **连得对**：关系只取受控词表类型并带方向、适用条件；`cooccurrence/hearsay/speculation/inference/common-knowledge` 一律不得作为直接关系证据。
3. **对得齐**：别名合并给依据；**跨篇相同表面默认不合并**（相同通用术语不代表两篇用了相同样品/模型/数据集/条件），除非别名规则显式声明适用两篇且类型一致。
4. **回得去**：每个节点和每条边都要有 `source_id + paragraph_id(JATS) + 原文短引`；位置是组织方 JATS 段落 ID，**不得把自建"第1页/page 1"当原 PDF 页码**（本包无 PDF 页码）。
5. **根标题作者归属**：根 DOI/title/authors 属于第一篇，不得套到第二篇；两篇各自用独立 source_id。
6. **诚实标注**：实体/关系是否忠实、别名是否真同指、证据是否支撑属价值判断，须 Agent 结合原文复核；脚本只做结构与规则校验，**绝不臆造实体、关系、证据或来源**。不交预制答案，处理平台给定真实案例。

## 工具：kg_engine.py

位置：`scripts/kg_engine.py`，纯 Python 3 标准库，无第三方依赖、无网络、不调用外部服务。

```bash
python scripts/kg_engine.py --help
python scripts/kg_engine.py pipeline input.json --outdir /app/output > result.json
```

### 子命令

| 子命令 | 关键输出 |
|--------|---------|
| `extract-entities` | `accepted/rejected`、`entities[].grounded/quote_in_source/entity_ok/issues` |
| `check-relations` | `accepted/rejected`、`relations[].relation_ok/issues`（weak_evidence_as_relation / cross_paper_unmarked 等） |
| `align-entities` | `merges`（含 basis）、`conflicts`（type_conflict / cross_paper_same_surface）、`canonical_of` |
| `bind-source` | `bound`、`quote_in_source`、`issues` |
| `query-graph` | `answers[].subgraph/evidence/traceable/unresolved_edges`、`all_traceable` |
| `incremental-update` | `existing_node_ids_preserved`、`changes`（added/merged/kept_conflicts/skipped）、`graph` |
| `check-export` | `machine_readable/serializable`、`missing_*_fields`、`duplicate_node_ids` |
| `pipeline` | `status`、`result`、`evidence`、`uncertainty` |

### 输入结构（pipeline）

```json
{
  "case_id": "案例标识",
  "source_index": {"P1": {"sec2.p3": "段落原文", "sec3.p1": "..."}, "P2": {...}},
  "known_papers": ["P1", "P2"],
  "entities": [{"id":"n1","surface":"CNN","type":"method","source_id":"P1",
                "paragraph_id":"sec2.p3","quote":"CNN方法","attribution":"self"}],
  "relations": [{"id":"e1","subject":"n1","relation":"uses","object":"n2",
                 "evidence_type":"direct","quote":"原文片段","condition":"样本/条件",
                 "source_id":"P1","paragraph_id":"sec4.p2","cross_paper":false}],
  "alias_rules": [{"canonical":"CNN","aliases":["卷积神经网络"],"source_ids":["P1"]}],
  "queries": [{"id":"Q1","type":"entity","surface":"CNN"},
              {"id":"Q2","type":"neighbor","node":"n1"},
              {"id":"Q3","type":"relation","relation":"compares"}],
  "export_format": "json"
}
```

- 实体类型：researcher / material / method / task / metric / conclusion / dataset / model / phenomenon
- 关系类型：uses / applies / proposes / compares / outperforms / measures / supports / contradicts / reports / derives-from / evaluated-on / achieves / correlates-with
- 强证据：direct / quoted / table / figure；弱证据（不得当直接关系）：cooccurrence / hearsay / speculation / inference / common-knowledge
- `attribution`：`self`（作者自述）或 `other`（他人/综述转述）
- 位置一律用 JATS 段落 ID（如 `sec2.p3`、`p1`、`fig2`），不是 PDF 页码

字段字典见 `references/`，最小可运行示例见 `examples/minimal_example.md`，冒烟输入/输出见 `examples/smoke_*.json`。

## 标准工作流

1. 读真实输入，识别各论文的 `source_id` 与段落原文，建立 `source_index`。
2. 抽取实体并逐条 `check_entity`：表面形式落地、类型合法、位置 JATS、短引命中、自述/转述分明。
3. 抽取关系并逐条 `check_relation`：受控类型+方向+条件+直接证据；跨篇关系必须 `cross_paper:true` 且有直接证据。
4. `align_entities` 处理别名与同名：同篇别名给依据合并，跨篇相同表面保留冲突节点。
5. `bind-source` 逐节点/边核验来源绑定；`query-graph` 执行**至少 3 个真实查询**并核对每个结果可回查；`pipeline.result.coverage_check` 的 `query_total>=3`、`query_traceable=query_total`、`graph_thin=false` 必须满足，否则补查询/补图谱，不带病导出。`pipeline --outdir /app/output` 会真实写出 `graph.json`、`query_answers.json`、`coverage_check.json`。
6. 如增量加入新论文，用 `incremental-update` 保留既有编号并记录新增/合并/冲突。
7. `check-export` 确认导出可读，`pipeline` 汇总。任何 `needs_attention` 项都要回到原文复核，不臆造补齐。

## 异常处理

- 论文缺失/无法解析：指出缺哪个 source_id，相关节点标 `no_source_id`，不编造正文。
- 实体同名冲突：`align-entities` 的 `conflicts` 显式保留为不同节点，附 `type_conflict` 或 `cross_paper_same_surface` 原因。
- 关系证据冲突：`check-relations` 把弱证据或跨篇无标注关系判为 rejected，不进入正式图。
- 查询无结果：`has_answer=false` 如实返回，不拿共现凑答案。


## 交付前自检（必须）

```bash
python scripts/validate_result.py --result /app/output/result.json --outdir /app/output --case /input/case.json --main-field graph
```

`valid=false` 时按 errors 修；`result.graph` 为空、顶层缺 `case_id/status/result/evidence/uncertainty`、或声明的产物路径不存在，都不得声称完成。

