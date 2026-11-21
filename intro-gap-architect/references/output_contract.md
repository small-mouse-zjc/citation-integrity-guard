# 输出契约（output_contract）

每个案例返回一份结构化结果 `result.json`，保留输入标识、主结果、证据/来源定位、运行状态与不确定性。

## 顶层字段

| 字段 | 类型 | 要求 |
|------|------|------|
| `case_id` | string | 与输入一致，不得丢失 |
| `status` | string | `ok` / `needs_attention` / `partial` |
| `result` | object | 四部件成稿 + 五项结构化检查结果 |
| `evidence` | object | 每条论断/空白/贡献的来源定位 |
| `uncertainty` | object | needs_review 清单 + 价值判断说明 |

## result 子字段（由 pipeline 产出）

| 字段 | 来源子命令 | 关键内容 |
|------|-----------|---------|
| `background_check` | detect-hype | `holds_up`、`hype_sentences`、`concrete_anchor_count` |
| `related_work_matrix` | group-matrix | `groups[]`（每组 works + comparison）、`needs_review` |
| `research_gap` | derive-gap | `gaps[]`（type/gap/supporting_works/reasoning/strength） |
| `contribution_alignment` | align-claims | `aligned`/`unbacked`/`inflated` |
| `citation_coverage` | coverage | `total`/`has_recent`/`missing_metadata` |
| `gap_to_contribution` | pipeline | 每条空白的 `bridged` 状态与对应 claim_id |
| `introduction_draft` | Agent 撰写 | 四部件连贯成稿（背景/相关工作/空白/贡献） |

## evidence 子字段

- `principles`：四原则（立得住/分得清/说得实/对得上）的落实说明；
- `gap_support`：每条空白 → 支撑文献 id 列表；
- `unbacked_claims`：悬空贡献 id 列表；
- 可追加 `claim_to_evidence`：贡献 id → 正文锚点定位。

## uncertainty 子字段

- `auto_grouped`：自动建议分组的文献数（须人工确认）；
- `needs_review`：待人工核验项清单；
- `note`：价值判断说明（转述忠实度、空白成立性、元数据真实性须 Agent 结合原文复核）。

## status 判定（引擎）

`ok`：背景立得住 + 贡献全对齐 + 元数据齐全 + 至少一条有证据的空白；否则 `needs_attention`。材料读取失败或严重缺失用 `partial` 并在 uncertainty 说明限制。

## 可编辑产物

引言成稿另存为文件（如 `introduction_draft.md` 或 `.docx`），路径写入 result。若平台要求 PDF/PNG 预览，须提供真实渲染文件，不得伪造。

## 最小示例（示意，非真实案例输出）

```json
{
  "case_id": "example-01",
  "status": "ok",
  "result": {
    "background_check": {"holds_up": true, "hype_count": 0},
    "related_work_matrix": {"group_count": 2, "works_covered": 5},
    "research_gap": {"gap_count": 2},
    "contribution_alignment": {"aligned_count": 3, "unbacked": [], "inflated": []},
    "gap_to_contribution": [{"gap": "标注成本高是多篇共同限制", "bridged": true}]
  },
  "evidence": {
    "gap_support": {"标注成本高是多篇共同限制": ["w1", "w2", "w4"]},
    "unbacked_claims": []
  },
  "uncertainty": {"auto_grouped": 1, "needs_review": [], "note": "转述忠实度须核对原文"}
}
```
