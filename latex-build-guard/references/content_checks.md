# 公式/表格/引用一致性检查

`check-content` 保证"改得对"——公式、表格、引用既符合原文意图，又符合模板要求。

## 公式

- 多行公式用 `align`/`gather`/`multline` 环境，对齐点 `&`，编号用 `\label{eq:xxx}` + `\eqref{eq:xxx}` 引用；
- 变量用斜体、函数名/单位用正体（`\sin`、`\mathrm{kg}`、`\siunitx`）；
- 公式含义要与正文叙述一致——脚本只检查结构与引用，语义核对由 Agent 回原文。

引擎检查：有公式环境但无 `eq:` 标签 → warning；`\ref/\eqref` 指向不存在的 label → `dangling_ref` error。

## 表格

- 三线表用 `booktabs` 的 `\toprule/\midrule/\bottomrule`，不用竖线；
- 列格式 `p{宽度}` 控制换行，宽表用 `tabularx`/`longtable`；
- 引擎解析 `tabular` 列格式做粗检，列数不匹配的实际错误由编译日志的 `table_error` 捕获。

## 交叉引用与文献

- 每个 `\label` 对应 `\ref/\eqref/\cref`，无孤立的未引用 label（warning 级可容忍）；
- `\cite{key}` 的键须在 `refs.bib` 有对应 `@article{key,...}` 条目；
- `.bib` 条目未被正文引用 → warning（可能冗余）；
- 含引用文档需多遍编译收敛。

引擎检查：`dangling_ref`（引用无 label）、`cite_no_bib`（cite 无条目）、`bib_uncited`（条目未被引用）。

## 模板必填项

通过 `template_required_fields` 传入期刊/会议/学位论文模板的必填项（如 `AuthorEmail`、`Abstract`、`Keywords`）。引擎检查这些标记是否在源码出现，缺失标 `template_required` error。具体版式约束（字号、行距、页边距）由模板 .cls 控制，Agent 须按模板文档核对。
