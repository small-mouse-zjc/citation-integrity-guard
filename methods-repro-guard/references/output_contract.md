# 输出契约（output_contract）

每个案例返回结构化结果 `result.json`，保留输入标识、主结果、证据/来源定位、运行状态与不确定性。

## 顶层字段

| 字段 | 类型 | 要求 |
|------|------|------|
| `case_id` | string | 与输入一致，不得丢失 |
| `status` | string | `ok` / `needs_attention` / `partial` |
| `result` | object | 五项结构化检查 + 章节草稿 |
| `evidence` | object | 数值来源定位、补造清单、四原则落实 |
| `uncertainty` | object | 追问清单、待作者确认、缺口数、价值判断说明 |

## result 子字段（pipeline 产出）

| 字段 | 来源子命令 | 关键内容 |
|------|-----------|---------|
| `completeness` | check-completeness | `elements`、`missing`、`complete` |
| `value_verification` | verify-values | `claims`、`unsupported`、`all_supported` |
| `reproducibility` | check-reproducibility | `items`、`missing`、`reproducible` |
| `gap_probe` | probe-gaps | `open_questions`、`generic_limitations` |
| `parameter_table` | build-param-table | `rows`、`missing_source` |
| `method_experiment_draft` | Agent 撰写 | 可编辑的方法与实验章节成稿 |

## evidence 子字段

- `principles`：写得全/准/做得着/说得住 四原则落实说明；
- `unsupported_values`：未找到来源的正文数值声称列表；
- `unsourced_params`：无来源参数名列表；
- `source_location`：数值声称 → 命中的来源名列表。

## uncertainty 子字段

- `open_questions`：待作者确认的追问清单（target/question/source）；
- `needs_author_confirmation`：是否有待确认项；
- `gap_count`：六要素缺失 + 复现缺项 + 补造数值 + 无来源参数 的总数；
- `note`：价值判断说明（数值语义一致性、限制成立性须 Agent 结合原文复核）。

## status 判定（引擎）

`ok`：六要素齐 + 数值全有来源 + 复现清单齐 + 参数全有来源 + 无套话限制；否则 `needs_attention`。材料读取失败或严重缺失用 `partial` 并在 uncertainty 说明。

## 可编辑产物

章节成稿另存为文件（`.md`/`.docx`），路径写入 result。平台要求 PDF/PNG 预览时须提供真实渲染文件，不得伪造。

## 最小示例（示意，非真实案例输出）

```json
{
  "case_id": "example-01",
  "status": "needs_attention",
  "result": {
    "completeness": {"present_count": 6, "complete": true},
    "value_verification": {"claim_count": 4, "unsupported_count": 1},
    "reproducibility": {"reproducible": false, "missing": [{"item":"seed"}]},
    "gap_probe": {"question_count": 2},
    "parameter_table": {"param_count": 5, "all_sourced": true}
  },
  "evidence": {
    "unsupported_values": ["批量大小为64"],
    "source_location": {"学习率为0.001": ["config.yaml"]}
  },
  "uncertainty": {
    "open_questions": [{"target":"数据集版本","question":"请确认数据集版本","source":"author_confirmation"}],
    "gap_count": 2,
    "note": "数值语义一致性须核对原文"
  }
}
```
