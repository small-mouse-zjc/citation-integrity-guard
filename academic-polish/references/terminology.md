# 术语表格式与锁定规则

## CSV 格式

```csv
source,target,forbidden
porosity,孔隙度,孔隙率;孔率
permeability,渗透率,渗透性
CNN,卷积神经网络,CNN网络;卷积网
```

- `source`：原文术语/缩写（必填）。
- `target`：锁定写法/译名（必填；英文单语润色时填 preferred spelling）。
- `forbidden`：禁用变体，分号分隔（可空）。
- UTF-8，一行一条；含逗号的字段加引号。

## JSON 格式

```json
{"terms": [{"source": "porosity", "target": "孔隙度", "forbidden": ["孔隙率"]}]}
```

## 锁定规则

1. **只锁原文已确定的写法**：原文用 `porosity` 就锁 `porosity`，不要另造新词。
2. **首次展开，后文统一**：`convolutional neural network (CNN)` 首次出现后统一 `CNN`；不要混用 `CNN network`。
3. **大小写敏感**：变量 `T`、`p`、`CO₂` 按原样；普通词按术语表。
4. **单位与符号**：`km2`→`km²` 之类只在原文本身不一致时统一；不改变数值。
5. **冲突不擅选**：术语表与原文冲突时保持原文，列入 `needs_author_confirmation`。
6. **中文/英文混排**：中文正文里的英文术语保留原文；不要自行翻译没有官方译名的词。

## 常见错误

- 全篇 `孔隙度`/`孔隙率` 混用 → `term_forbidden`。
- 摘要用 `CNN`，正文用 `卷积神经网络` 且未声明同义 → 至少统一首次展开，后文择一。
- 把 `permeability` 改成 `渗透性` 而术语表锁 `渗透率` → `term_missing`。
