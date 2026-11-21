# 来源绑定与 JATS 位置规范

## 每个节点和每条边都要三件套

| 字段 | 含义 | 校验 |
|------|------|------|
| `source_id` | 论文标识（如 P1/P2），与 corpus-manifest 的 DOI 对应 | 必须在 known_papers 中；否则 unknown_source_id |
| `paragraph_id` | 组织方 JATS 段落 ID | 必须匹配 JATS 格式；伪页码 → fake_pdf_page |
| `quote` | 原文短引（尽量短、可唯一定位） | 必须能在该段落原文命中；否则 quote_mismatch |

## JATS 段落 ID 格式

合法示例：`sec2.p3`、`p1`、`p0012`、`abs1`、`title`、`fig2`、`tbl1`、`fn1`、`sec3.1.p5`、`app1`。

正则：`^(abs|abstract|title|p|sec|fn|tbl|tab|fig|app|suppl)[\w.\-]*$`（不区分大小写）。

**禁止**：把自建"第1页""page 1""p.1""PDF页1"当成原文位置。题面本包无 PDF 页码，位置是 JATS 段落 ID。把页码当位置 → `fake_pdf_page`，节点/边的 bound 判 false。

`bind-source` 子命令逐条核验：`bound = 有source_id 且 段落JATS合法 且 有quote 且 quote在原文命中（若给了 source_index）`。

## 证据回查

- `check_entity` / `bind_source` 在给了 `source_index` 时会实际到 `{source_id: {paragraph_id: text}}` 里查 `surface` 与 `quote`，不做"看着像就算"。
- `query-graph` 的每个答案汇总 evidence（节点+边），`traceable=true` 要求每条 evidence 都有 source_id + paragraph_id + quote；给了 source_index 时还回填 `quote_in_source`。
- 弱证据关系单列 `unresolved_edges`，不混进支撑证据。

## 冲突与未报告

- 源内冲突（同一论文两种说法）→ 在 uncertainty 说明，不强行择一写成事实。
- 未报告项 → 明确标"未报告/无法判断"，不推断数值。
- 只有同篇多种文件格式（JSON + Markdown 同篇）不算跨篇证据；两篇独立 DOI 才算两篇。
