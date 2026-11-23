# 输出契约（output_contract）

## 顶层

| 字段 | 类型 | 要求 |
|---|---|---|
| `case_id` | string | 与输入一致 |
| `status` | string | `success` / `needs_attention` / `partial` |
| `result` | object | 章节成稿 + 五项检查 + 参数表 |
| `evidence` | object | 四问落实 + 来源定位 + 补造/无来源清单 |
| `uncertainty` | object | 追问 + 待作者确认 + 缺口数 |

## result

| 字段 | 必填 | 内容 |
|---|---|---|
| `method_experiment_draft` | 是 | 完整方法与实验章节（>=200 字符；通常 1500–5000 字） |
| `draft_metrics` | 是 | `chars`、`present`、`required_min_chars` |
| `completeness` | 是 | 六类要素 `elements/missing/complete` |
| `value_verification` | 是 | `claims/unsupported/all_supported` |
| `reproducibility` | 是 | `items/missing/reproducible` |
| `gap_probe` | 是 | `open_questions/generic_limitations/needs_author_confirmation` |
| `parameter_table` | 是 | `rows/missing_source/all_sourced` |
| `delivery` | 是 | 成稿/检查/参数表路径 |
| `summary` | 是 | 一行结论 |

## status 判定

- `success`：章节成稿非空、六要素齐全、数值有来源、复现清单齐全、参数有来源、无套话限制；
- `needs_attention`：成稿已完成，但仍有缺口/待作者确认；
- `partial`：`method_experiment_draft` 缺失或 <200 字符，或材料不可读，只完成部分要素。

**只交检查结果、不交章节成稿，一律 partial。**

## evidence

- `principles`：写得全/写得准/做得着/说得住 的落实；
- `source_location`：数值 → 文件:行/字段；
- `unsupported_values`：找不到来源的数值；
- `unsourced_params`：无来源参数。

## uncertainty

- `open_questions`：需作者/实验者回答的问题；
- `needs_author_confirmation`：冲突值、版本、条件；
- `gap_count`：缺口总数；
- `note`：脚本只做集合比对，语义/条件一致性由 Agent 复核。

## 可编辑产物

- `/app/output/method_experiment_draft.md`：章节全文；
- `/app/output/parameter_table.csv`：名称,取值,单位,作用对象,来源；
- `/app/output/checks.json`：pipeline 结果。

## 最小示例（示意，非正式答案）

```json
{
  "case_id": "example-05",
  "status": "success",
  "result": {
    "method_experiment_draft": "# 方法\n## 3.1 总体流程\n...",
    "draft_metrics": {"chars": 2600, "present": true, "required_min_chars": 200},
    "completeness": {"complete": true, "missing": []},
    "value_verification": {"all_supported": true, "unsupported": []},
    "reproducibility": {"reproducible": true, "missing": []},
    "gap_probe": {"generic_limitations": []},
    "parameter_table": {"all_sourced": true, "missing_source": []},
    "delivery": {"draft_md": "/app/output/method_experiment_draft.md"},
    "summary": "六要素齐全；参数 6 个均有来源；复现清单 6 项；缺口 2 条已交作者"
  },
  "evidence": {"source_location": {"lr=0.001": ["config.yaml:3"]}},
  "uncertainty": {"open_questions": ["数据集版本待确认"], "gap_count": 1}
}
```
