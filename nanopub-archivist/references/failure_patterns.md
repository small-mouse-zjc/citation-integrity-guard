# 失败模式库（阅读14 Nanopublication）

按四问列出常见失败与降级处置：

- **拆得细**：整段塞进一个断言字段 → 用 `assertion_checks*` 检出，见 SKILL.md 门禁。
- **对得上**：断言无最小证据片段 → 用 `evidence_bindings*` 检出，见 SKILL.md 门禁。
- **追得回**：作者/年份/版本链路不全 → 用 `provenance.missing` 检出，见 SKILL.md 门禁。
- **读得懂**：导出字段不全无法机读 → 用 `export_check.missing_fields+export_check.serializable*` 检出，见 SKILL.md 门禁。

材料不足/格式未知/外部核验失败一律显式标注，不臆造。
