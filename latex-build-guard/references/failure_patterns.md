# 失败模式库（写作13 LaTeX 写作与编译）

按四问列出常见失败与降级处置：

- **编译得通**：报错停第一条不定位根因 → 用 `error_classification.errors*+error_classification.cascading*` 检出，见 SKILL.md 门禁。
- **改得对**：公式表格交叉引用不符原文 → 用 `content_check.issues` 检出，见 SKILL.md 门禁。
- **交得可用**：把PDF/截图当交付 → 用 `deliverable_check.usable*+deliverable_check.issues` 检出，见 SKILL.md 门禁。
- **复现得了**：缺版本/命令无法复现 → 用 `reproducibility_check.missing` 检出，见 SKILL.md 门禁。

材料不足/格式未知/外部核验失败一律显式标注，不臆造。
