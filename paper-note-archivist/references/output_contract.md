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


## 端到端交付（完成器 solve / render-draft）

### 真实输入字段（solve 适配）

`solve case.json --out /app/output` 读取 case.json，支持以下真实输入字段（读不到不臆造，记入 `adapter_notes`）：

- `paper_sections`：内联章节数组（优先）。
- `paper_text`：论文全文，按段落/章节标题行切段为章节骨架。
- `section_files`：`[路径]` 或 `{章节名:路径}`，读取 `.txt`/`.md`（切段）或 `.json`（含 `paper_sections`/`card`）。
- `card` / `card_*`：六字段论文卡片（研究问题/数据/方法条件/主要发现/局限/结论前提）。
- `notes`、`notes_text`（按行切条）、`notes_files`（`{锚点:路径}`）：真实笔记条目。
- `valid_anchors`、`knowledge_points`、`dup_threshold`：锚点定位表、知识点与去重阈值。

### 输出：solve result.json

```json
{
  "case_id": "...",
  "status": "ok | needs_attention | partial",
  "input_mode": "case",
  "source_count": 7,
  "adapter_notes": ["notes_text 切条 2"],
  "result": {
    "draft_text": "# 逐章笔记\n## 摘要\n  - [n1] ...（第5页）\n# 论文卡片\n- 研究问题：...\n# 知识点\n- ...",
    "chapter_blocks": [
      {"section":"摘要","notes":[{"id":"n1","text":"...","anchor":"第5页"}],"status":"ok"}
    ],
    "reading_card": {"question":{"value":"...","status":"reported","label":"研究问题"}},
    "knowledge_entries": [{"label":"CNN","definition":"...","anchor":"§2"}],
    "section_alignment": {...}, "card_fields": {...}, "anchor_verification": {...},
    "structured_notes": [...],
    "summary": "逐章笔记 7 章；卡片 6/6 字段；锚点回链 2/2；知识点 2 条"
  },
  "needs_review": ["卡片字段『数据』未报告", "笔记 n3 锚点悬空/无效"],
  "uncertainty": ["章节/笔记/卡片字段只取真实输入；缺的标〔待补〕，不臆造内容或锚点"],
  "delivery": {"written":true,"path":"/app/output/result.json","bytes":5343}
}
```

- `result.draft_text`：可编辑逐章结构化笔记成稿：逐章笔记 + 六字段卡片 + 知识点 + 锚点回链；**缺字段标〔待补：原文未报告〕、缺锚点标〔待补：无锚点〕，不臆造内容或锚点**。
- `result.chapter_blocks`：逐章笔记（section → 命中笔记 → 锚点）；未被章节吸收的笔记进 `orphan_notes`（在 draft_detail 中）。
- `result.reading_card`：六字段卡片，每字段 `status=reported|not_reported`。
- `status`：`ok`=章节/字段/锚点/知识点齐全且核验干净；否则 `needs_attention`/`partial`，缺口进 `needs_review`。
- `delivery`：落盘回执；`written=true` 且 `bytes>0` 才算交付成功。异常不静默吞错，写入 `input_error` 或显式降级。

### render-draft / pipeline --with-draft

`render-draft input.json` 与 `pipeline input.json --with-draft` 在输出中给出 `draft_detail`（含 `draft_text`/`chapter_blocks`/`reading_card`/`knowledge_entries`/`needs_author_confirmation`）；默认 `pipeline` 不含成稿。两者都不臆造内容，缺项标〔待补〕。
