# 证据定位与自检契约（Evidence Contract）

对应题面"核得回"：每段文字、每张表格能指回原文页码与区块，读不出的部分如实标注，不靠猜补齐。

## 1. 证据索引（build_evidence）

每个块生成一条证据记录：

```json
{
  "id": "B001",
  "page": 1,
  "bbox": [72.0, 100.0, 520.0, 114.0],
  "block_type": "text",
  "text_head": "Abstract",
  "source_line": 3
}
```

- `id` 前缀区分类型：`B`=正文块、`S`=章节、`T`=表格、`X`=被剔除项。
- `page`：原文页码（1-based）。
- `bbox`：`[x0,y0,x1,y1]`，区块在页面上的位置；无法定位者为 null。
- `block_type`：`text` / `section:<kind>` / `table` / `excluded:<reason>`。
- `text_head`：文本前 40 字，便于人工核对。
- `source_line`：回指 `clean.lines` 的原始行号，可回溯到 spans。

## 2. 自检项（verify）

| 检查 | 判据 | 不通过进 problems |
|------|------|-------------------|
| 正文字符覆盖率 | `out_chars / body_chars ≥ 0.90` | 低于 90% 提示检查断行吞字 |
| 阅读顺序 | `order_violations` 为空 | 页码/ y 回退 |
| 乱码缺字 | `unreadable` 列表 | 有则提示已如实标注 |
| 证据块 | 每块有 page 与 block_type | 缺失则告警 |

- `coverage` 分母 `body_chars` 只算正文区（排除页眉页脚边注），避免被剔除内容拉低。
- `consistent=true` 当且仅当无 problems。

## 3. 诚实标注原则

- **乱码/缺字**：`REPLACEMENT_RE` 命中连续替换符/方块 → `unreadable`，保留原样，不猜字。
- **页眉页脚/边注**：进 `dropped` 附 `reason`，不算正文、不丢证据。
- **扫描件/无文字层**：`extract` 返回 `status=needs_review` + `note`，不把 0 行当成功。
- **加密/损坏 PDF**：`extract` 返回 `cannot_open_pdf`，说明原因。
- **跨页续表/合并单元格**：给候选、`needs_review`，不替作者决定。

## 4. 与平台 output_contract 的映射

平台的"证据与边界"字段 ← `evidence_index` + `verification.problems` + `clean.unreadable`；
"运行状态"字段 ← `status` + `problems` + 降级说明；
"阅读/解析结果"字段 ← `reading_text` + `tables` + `formulas` + `captions`。

## 边界

覆盖率是字符数比，不等于语义正确；高覆盖率仍可能有错字，需结合 `unreadable` 与人工抽查。证据 bbox 依赖输入坐标准确；若上游提取层坐标失真，需重新导出。
