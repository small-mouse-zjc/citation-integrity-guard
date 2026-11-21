# 可复用词表（vocabulary）

独立维护、供他人复用的标识符词表。脚本内已内联等价规则以保证零外部依赖；本文件是**可维护副本**，更新时同步 `citation_engine.py` 对应常量。纯 UTF-8 文本，无第三方依赖。

## 1. 预印本 DOI 前缀（用于 version_variant 判据）

```
10.48550/arxiv.      arXiv
10.1101/             bioRxiv / medRxiv
10.21203/            Research Square
10.2139/ssrn.        SSRN
10.31234/osf.        OSF Preprints
10.13140/            Zenodo
```
判据含义：当两条标题近、作者同、年份不同，且 DOI 命中上述前缀之一与期刊 DOI 对照时，判为"疑似预印本与正式版"，`not_merged` + `needs_review`。

## 2. 题名归一化噪声词（去噪后再比对）

```
英文停用词：the a an of and or in on for to with by is are was were this that we our their its as at from using based
中文停用词：的 了 和 与 及 在 是 为 对 中 该 这 其 并 等 也 而 从 以 于 上 下
```
实现见 `_content_words` / `_norm_text`。去噪目的：避免"的/the"等高频词稀释主题重叠 score。

## 3. 字段别名映射（跨导出格式归一）

BibTeX → 统一字段：
```
title→title, author→authors, journal/journaltitle→journal, booktitle→booktitle,
year/date→year, number→issue, pages→pages, doi→doi, publisher→publisher,
address→address, school→school, institution→institution, abstract→abstract
```

RIS → 统一字段：
```
TY→type, TI/T1→title, AU/A1→authors, PY/Y1→year, JO/JF/JA→journal,
VL→volume, IS→issue, SP+EP→pages, DO→doi, AB→abstract, PB→publisher, KW→keywords
```

CNKI/中文键值 → 统一字段：
```
题名/篇名→title, 作者→authors, 来源/期刊→journal, 年份/年→year,
卷→volume, 期→issue, 页码/页→pages, DOI→doi, 摘要→abstract
```

## 4. 文献类型标识（GB/T 7714—2015）

```
article/journal→[J]   book→[M]    thesis/phdthesis/mastersthesis→[D]
conference/inproceedings→[C]      report→[R]   standard→[S]
patent→[P]            online/electronic/preprint→[EB/OL]   misc→[Z]
```

## 5. 数据论断信号词（place 落点定位）

```
表明 显示 发现 证明 证实 指出 报道 提出 首次 显著 提高 降低 减少 增加 达到
优于 高于 低于 约为 高达 准确率 精度 召回率 我们 本文 作者
```
配合"带单位数据/小数/百分数"数值信号；"表1/图2/第3章"等编号由 `REF_NUM` 先行剥离，不算数据论断。
