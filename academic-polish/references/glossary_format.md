# 术语表格式（glossary）

## JSON（推荐）

```json
{"glossary": [
  {"source": "porosity", "target": "孔隙度", "scope": "global"},
  {"source": "permeability", "target": "渗透率", "scope": "global"}
]}
```

## TSV / CSV（两列）

```text
porosity\t孔隙度
permeability\t渗透率
```

## 一致性检查（check_terms）

- **source_multi_target**：同一源术语对应多个译法/写法（大小写归一）——须统一。
- **target_multi_source**：多个术语写成同一形式——可能误合并，须确认。
- **unlisted_abbreviations**：稿件中出现但术语表未收录的全大写缩写——须补首次出现全称。

术语表经 `glossary_basis` 进入逐句草稿，确保每处术语用法可回查。
