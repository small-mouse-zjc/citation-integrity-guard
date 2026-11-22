# 守护元素规则（protect / check_preserve）

润色前后必须保持一致的元素，脚本先抽取占位再逐项核对：

| 类别 | 模式 | 守恒要求 |
|-|-|-|
| number_unit | 数字+单位/百分号 | 数值与单位不得被改 |
| number | 裸数字（含小数/科学计数） | 不得增删改（引用内数字优先归 citation） |
| citation | `[1]`/`[1,2]`/`[1-3]`/`[@key]` | 引用编号不得改 |
| refmark | `Fig. 2`/`Table 3`/`式(1)` 等 | 图表公式指向不得改 |
| formula | `x = ...` | 公式不得被改写 |
| chemical | `CO2`/`H₂O`/`NaCl` 等 | 化学式不得被改 |
| limit | 限定/弱化/绝对词（分强度档） | 弱化词不得丢；原文无绝对词时不得新增 |
| negation | `not`/`no`/`不`/`未`/`无` 等 | 否定词不得丢（否则反转原意） |

优先级：结构化标记（citation/refmark/formula/chemical）先于裸数字，避免 `[1]` 被拆。

守恒告警类型：`protected_lost` / `protected_added` / `negation_lost` /
`hedge_weakened`（弱化词丢失＝结论边界被加强）/ `claim_strengthened`（新增绝对化词）。
