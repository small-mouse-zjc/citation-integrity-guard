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
| `assertion_coverage` | coverage_check | `ok`、`assertion_count`、`recommended_min_assertions`、`uncovered_sentences`、`issues` |
| `nanopublications` | pipeline 组装 | 每条含 assertion/subject/relation/object/evidence/evidence_location/evidence_type/paper/authors/year/version/identifier/confidence |
| `artifacts` | pipeline（有 `--outdir` 时） | `nanopublications.json` / `assertion_evidence_map.json` / `outdir` 的真实路径 |

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

`ok`：所有断言证据绑定成功 + 来源元数据齐全 + 导出合规 + 无重复断言 + `assertion_coverage.ok=true`（断言数达到建议下限且每个原句被覆盖）；否则 `needs_attention`。材料缺失（扫描版无文本层、原文不可访问）用 `partial`，并列出限制。

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
