# 目标规范扩展映射（以 APA 7th 为例）

本技能内置主规范为 **GB/T 7714—2015 顺序编码制**（`format_entry_gb`）。题面允许"指定 APA 版本等其他规范"。本文档证明规范扩展机制可用：`format_entry_apa` 已作为第二个规范落地，`format_bib(standard="apa")` 可切换。复用者可按同样方法扩展到APA 6th、MLA、Chicago 或其他指定版本。

## 扩展三步法

1. **字段映射**：把统一 `entries` 结构（title/authors/year/journal/volume/issue/pages/doi/type/publisher…）映射到目标规范的字段顺序。
2. **规则函数**：新增 `format_entry_<style>(entry)` 返回单条字符串；遵守"缺字段不臆造、DOI 保留、类型标识按规范"的共同约束。
3. **注册**：在 `format_bib` 增加 `standard` 分支，并在 `TYPE_LABEL`/类型映射处补齐该规范的类型表达。

## GB/T 7714 vs APA 7th 关键差异（已实现的映射）

| 维度 | GB/T 7714—2015 | APA 7th（本技能展示实现） |
|------|----------------|---------------------------|
| 编号 | 顺序编码 `[1]` 前缀 | 著者—出版年，无顺序编号 |
| 作者 | 列前 3 位，中文第 4 位起", 等"，英文", et al." | 姓在前名缩写在后；2 人用 `&`；3–6 人全列；>6 人列前 6 加 `...` |
| 年份位置 | 期刊名之后 | 作者之后的括号 `(2020)` |
| 题名后 | 文献类型标识 `[J]/[M]/[D]` | 无类型标识，句首大写 |
| 卷期页 | `期刊, 年, 卷(期): 起-止.` | `期刊, 卷(期), 起-止.` |
| DOI | `DOI: 10.x/...` | `https://doi.org/10.x/...` |

## 调用

```bash
python scripts/citation_engine.py format input.json --standard apa
# 或在 Python 中：
# from citation_engine import format_bib
# format_bib(entries, standard="apa")
```

## 边界声明

`format_entry_apa` 是"规范可扩展"的展示实现，覆盖作者、年份、题名、期刊卷期页、DOI 的主干规则。APA 对地道英文大小写、地名的出版地省略、编辑/译者、DOI 大小写等有更细的版本细则，正式投稿须人工核对；本技能不冒充完整 APA 排版器。同理，扩展到 MLA/Chicago 需按上表方法补齐各自细则并标注边界。
