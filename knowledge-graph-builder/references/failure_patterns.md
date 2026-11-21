# 失败模式库（阅读15 文献知识图谱构建）

按四问列出常见失败与降级处置：

- **抽得准**：凭常识补概念非论文实证实体 → 用 `entity_extraction.rejected` 检出，见 SKILL.md 门禁。
- **连得对**：把共现/推测当直接证据 → 用 `relation_check.rejected` 检出，见 SKILL.md 门禁。
- **对得齐**：别名未合并或同名误并 → 用 `entity_alignment.merges+entity_alignment.conflicts` 检出，见 SKILL.md 门禁。
- **查得到回得去**：查询无来源可回溯 → 用 `graph_query.all_traceable*` 检出，见 SKILL.md 门禁。

材料不足/格式未知/外部核验失败一律显式标注，不臆造。
