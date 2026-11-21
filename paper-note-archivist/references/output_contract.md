# 输出契约（output_contract）

每个案例返回结构化结果 `result.json`，保留输入标识、主结果、证据定位、运行状态与不确定性。

## 顶层字段

| 字段 | 类型 | 要求 |
|------|------|------|
| `case_id` | string | 与输入一致 |
| `status` | string | `ok` / `needs_attention` / `partial` |
| `result` | object | 五项结构化检查 + 结构化笔记 |
| `evidence` | object | 四原则落实 + 缺锚点/坏锚点/知识点合并 |
| `uncertainty` | object | 未报告字段 + 待确认归一 + 价值判断说明 |

## result 子字段（pipeline 产出）

| 字段 | 来源子命令 | 关键内容 |
|------|-----------|---------|
| `section_alignment` | check-section-alignment | `order_consistent`、`missing_sections`、`inversions` |
| `card_fields` | check-card-fields | `fields`、`missing`、`complete` |
| `anchor_verification` | verify-anchors | `anchored_count`、`no_anchor`、`bad_anchor` |
| `knowledge_normalization` | normalize-knowledge | `entries`、`merges`、`needs_review` |
| `reading_card` | build-reading-card | 统一字段卡片（含 not_reported） |
| `structured_notes` | 输入/Agent | 按论文章节组织、带锚点的可编辑笔记 |

## evidence 子字段

- `principles`：对得上/留得住/找得回/用得上 落实说明；
- `missing_anchors`：缺锚点的笔记 id；
- `bad_anchors`：锚点无效的笔记 id；
- `knowledge_merges`：知识点合并记录。

## uncertainty 子字段

- `missing_fields`：卡片缺失字段 + 未报告字段；
- `needs_review`：待人工确认的归一（中英同义、低相似合并）；
- `note`：价值判断说明（笔记忠实度、锚点对应性须结合原文复核）。

## status 判定（引擎）

`ok`：章节对齐 + 字段齐 + 笔记全锚定 + 无待确认归一；否则 `needs_attention`。PDF 读取失败或严重缺失用 `partial`。

## 阅读/解析结果要求

- 覆盖任务要求（章节总结/卡片/知识点/锚点）；
- 每个关键结论可回到材料定位（页码/章节/图表）；
- 未报告和不确定项明确标注，不写成事实；
- 运行状态（成功/部分/无法判断）与异常原因清楚。

## 可编辑产物

笔记成稿另存为文件（`.md`/`.docx`），路径写入 result。平台要求 PDF/PNG 预览时提供真实渲染文件，不得伪造。

## 最小示例（示意，非真实案例输出）

```json
{
  "case_id": "example-01",
  "status": "needs_attention",
  "result": {
    "section_alignment": {"order_consistent": true, "missing_sections": ["discussion"]},
    "card_fields": {"present_count": 5, "complete": false},
    "anchor_verification": {"anchored_count": 3, "no_anchor": [{"id":"n4"}]},
    "knowledge_normalization": {"entry_count": 8, "merged_count": 2}
  },
  "evidence": {"missing_anchors": ["n4"], "bad_anchors": []},
  "uncertainty": {
    "missing_fields": [{"label":"结论前提"}],
    "note": "笔记忠实度与锚点对应性须结合原文复核"
  }
}
```
