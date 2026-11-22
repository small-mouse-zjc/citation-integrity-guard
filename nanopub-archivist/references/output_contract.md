# 输出契约（output_contract）

每个案例返回结构化结果 `result.json`，保留输入标识、主结果、证据定位、运行状态与不确定性。

## 顶层字段

| 字段 | 类型 | 要求 |
|------|------|------|
| `case_id` | string | 与输入一致 |
| `status` | string | `ok` / `needs_attention` / `partial` |
| `result` | object | 六项结构化检查 + nanopublications |
| `evidence` | object | 四原则落实 + unbound_assertions + missing_provenance |
| `uncertainty` | object | needs_review + 说明 |

## result 子字段（pipeline 产出）

| 字段 | 来源子命令 | 关键内容 |
|------|-----------|---------|
| `source_paragraph` | 输入 | 原始结论段落 |
| `assertion_checks` | check-assertion | 每条断言的 `relation`、`has_qualifier`、`atomicity_ok`、`issues` |
| `evidence_bindings` | bind-evidence | `bound`、`has_anchor`、`word_overlap`、`issues` |
| `provenance` | check-provenance | `complete`、`missing`、`metadata` |
| `export_check` | check-export | `machine_readable`、`serializable`、`missing_fields`、`issues` |
| `quality_check` | check-quality | `duplicate_assertions`、`ambiguous_subjects`、`subject_count` |
| `nanopublications` | pipeline 组装 | 每条含 assertion/subject/relation/object/evidence/evidence_location/evidence_type/paper/authors/year/version/identifier/confidence |

## nanopublication 字段字典

| 字段 | 含义 | 必填 |
|------|------|------|
| `assertion` | 原子断言全文（单一可判断真假） | 是 |
| `subject` | 断言主体（研究对象/方法） | 是 |
| `relation` | 受控关系（见 provenance_vocab.md） | 是 |
| `object` | 断言客体（数值/结论/类别） | 是 |
| `evidence` | 最小充分证据片段 | 是 |
| `evidence_location` / `anchor` | 原文位置（页码/章节/图表/段落） | 是 |
| `evidence_type` | `direct` 直接证据 / `indirect` 间接推论 | 是 |
| `paper` | 论文题名 | 是 |
| `authors` | 作者列表 | 是 |
| `year` | 发表年份 | 是 |
| `version` | 版本/预印本版本 | 是 |
| `source` | 期刊/会议/来源 | 是 |
| `identifier` | DOI / PMID | 是 |
| `confidence` | `high` / `medium` / `low`，附依据 | 是 |

## evidence 子字段

- `principles`：拆得细 / 对得上 / 追得回 / 读得懂 四原则落实说明；
- `unbound_assertions`：证据绑定失败的断言索引列表；
- `missing_provenance`：来源缺失字段名列表。

## uncertainty 子字段

- `needs_review`：含 issue 的断言索引 + 含 warning 的证据索引，须 Agent 逐条人工复核；
- `note`：说明断言忠实性、证据支撑性、置信度属价值判断，脚本只做结构与规则校验，不臆造断言或证据。

## status 判定（引擎）

`ok`：所有断言证据绑定成功 + 来源元数据齐全 + 导出合规 + 无重复断言；否则 `needs_attention`。材料缺失（扫描版无文本层、原文不可访问）用 `partial`，并列出限制。

## 目标产物要求

- `result.json` 保留 `case_id` 与全部契约字段；
- 每条断言可回到原文定位（证据片段 + 位置 + 来源）；
- 价值判断项在 uncertainty 中显式声明，不写成既成事实。

## 示例（节选自 examples/smoke_output.json）

```json
{
  "case_id": "smoke",
  "status": "ok",
  "result": {
    "assertion_checks": [{"relation": "improves", "has_qualifier": true, "atomicity_ok": true}],
    "evidence_bindings": [{"bound": true, "has_anchor": true}],
    "provenance": {"complete": true},
    "export_check": {"machine_readable": true, "missing_fields": []},
    "quality_check": {"duplicate_assertions": []},
    "nanopublications": [{"assertion": "CNN方法在碳酸盐岩薄片达到0.92准确率", "relation": "improves"}]
  }
}
```


## 端到端交付（完成器 solve / render-draft）

### 真实输入字段（solve 适配）

`solve case.json --out /app/output` 读取 case.json，支持以下真实输入字段（读不到不臆造，记入 `adapter_notes`）：

- `paragraph` / `source_text`：真实论文段落文本。
- `source_files`：`[路径]`，读 `.txt`/`.md`（并入源文本）或 `.json`（含 `assertions`/`source_metadata`/`paragraph`）。
- `assertions` / `assertions_file`：内联断言数组或真实断言 JSON 文件。
- `source_metadata` / `metadata_file`：内联来源元数据或真实 JSON 文件。
- `export_format`：导出格式（json/jsonld/rdf）。

### 输出：solve result.json

```json
{
  "case_id": "...",
  "status": "ok | needs_attention | partial",
  "input_mode": "case",
  "assertion_count": 1,
  "adapter_notes": ["文本:paper.txt"],
  "result": {
    "draft_text": "# Nanopublication 交付稿（可编辑）\n## 源段落\n...\n## 结构化断言\n### NP1\n- 断言：...\n## 来源链路\n...\n## 导出（json）\n```json ...```",
    "nanopublications": [{"assertion":"...","subject":"...","relation":"...","object":"...","evidence":"...","evidence_location":"§4"}],
    "export_text": "[{"assertion": ...}]",
    "assertion_checks": [...], "evidence_bindings": [...], "provenance": {...},
    "export_check": {...}, "quality_check": {...},
    "summary": "断言 1 条；证据绑定 1/1；来源字段 6/6；导出合规；重复 0"
  },
  "needs_review": ["断言1 证据：断言与证据词面无重叠，须人工确认"],
  "uncertainty": ["断言/证据/元数据只取真实输入；无断言标〔待补〕，不臆造断言或证据"],
  "delivery": {"written":true,"path":"/app/output/result.json","bytes":4049}
}
```

- `result.draft_text`：可编辑 Nanopublication 交付稿：结构化断言（断言-三元组-证据-锚点-置信度）+ 来源链路 + 导出；**无真实断言标〔待补：无真实断言〕，不臆造断言或证据**。
- `result.nanopublications` / `export_text`：从真实断言组装的 nanopub 列表与按 `export_format` 序列化的导出文本。
- `status`：`ok`=证据全绑定 + 来源完整 + 导出合规 + 无重复；否则 `needs_attention`/`partial`，缺口进 `needs_review`。
- `delivery`：落盘回执；`written=true` 且 `bytes>0` 才算交付成功。异常不静默吞错，写入 `input_error` 或显式降级。

### render-draft / pipeline --with-draft

`render-draft input.json` 与 `pipeline input.json --with-draft` 在输出中给出 `draft_detail`（含 `draft_text`/`nanopublications`/`export_text`/`needs_author_confirmation`）；默认 `pipeline` 不含成稿。两者都不臆造断言或证据，缺口标〔待补〕。
