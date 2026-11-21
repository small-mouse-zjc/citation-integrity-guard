# 来源元数据与受控关系词表（provenance_vocab）

## 六项来源元数据（PROV_FIELDS）

| 字段 | 说明 | 核验规则 |
|------|------|---------|
| `paper` | 论文题名 | 非空 |
| `authors` | 作者列表 | 非空列表 |
| `year` | 发表年份 | 非空 |
| `version` | 版本 / 预印本版本 | 非空（无版本写"正式发表版"等，不留空） |
| `source` | 期刊 / 会议 / 来源 | 非空 |
| `identifier` | DOI / PMID | 非空且格式合规 |

`check_provenance` 逐字段查缺失；标识符须以 `doi:` 开头、含 `doi.org`、匹配 `10.xxxx`，或以 `PMID` 开头，否则报 `identifier_format`。缺项一律显式列入 `missing`，不臆造。

## 受控关系词表（RELATION_VOCAB）

引擎按下列词表把中文/英文表述统一映射到规范关系（正则、大小写不敏感）：

| 规范关系 | 触发词（中/英） |
|---------|----------------|
| `indicates` | 表明、指示、显示、indicate、suggest、show |
| `causes` | 导致、引起、造成、cause、lead to、result in |
| `correlates` | 相关、关联、correlate、associate |
| `improves` | 提升、改善、提高、优于、达到、达至、improve、outperform、better than、achieve |
| `reduces` | 降低、减少、下降、reduce、decrease、lower |
| `is_a` | 属于、是一种、是、is a、is an、be a |
| `consistent_with` | 一致、符合、consistent、agree |
| `contradicts` | 矛盾、不一致、冲突、contradict、conflict |

未命中任何关系词 → `issues[].type=no_relation`，须改写断言或补关系字段。一个断言只取一个关系；多关系说明该拆了。

## 限定词信号（QUALIFIERS）

存在这些信号时，`overbroad` 警告不触发：

- 条件：`在……条件`、`当……时`、`under`、`given`、`within`；
- 量化：`约`、`大约`、`左右`、`approximately`、`about`、`部分`、`某些`、`特定`；
- 数值：`\d+%`、`\d+\.\d+`。

## 锚点正则（ANCHOR_RE）

见 `evidence_binding.md`。页码、章节、图表、段落、行号五类。

## 词表维护

受控词表与判据参数集中在 `scripts/nanopub_engine.py` 顶部常量区（RELATION_VOCAB / OVERBROAD / QUALIFIERS / ANCHOR_RE / COMPOUND）。扩展领域关系时在此处增补，同步更新本文档与 `examples/selftest.py` 对应用例。
