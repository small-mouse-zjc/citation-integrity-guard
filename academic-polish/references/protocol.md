# 保源最小编辑协议（Protocol）

## 1. 目标

把"语言更好"与"事实不变"同时做到。润色不是改写内容，而是在不改变事实、引用、断言强度和术语体系的前提下，修正语法、提升表达、统一语域。

## 2. 五条不变量

| 代号 | 不变量 | 检查方法 |
|---|---|---|
| N | 数字、单位、样本量、年份、公式编号不增不减不改值 | `polish_audit.py check` 的 `number_missing/new_number` |
| C | 引用、交叉引用、图表/式编号原样保留 | `citation_missing/citation_added` |
| H | 限定强度与否定方向不变 | `hedge_dropped/booster_added/negation_dropped` |
| T | 术语、缩写、大小写全篇统一 | `term_missing/term_forbidden` |
| M | 最小编辑，不整段重写 | `heavy_rewrite/large_rewrite` |

## 3. 六个阶段

1. **Intake**：读真实输入，建事实台账（段落/句子/数字/引用/限定/否定/标题/图表指向）。
2. **Termbase**：锁定术语与语域；不新造译名、不新造缩写。
3. **Revision**：逐句做 G/T/R 编辑；只改语言层，不动 N/C/H。
4. **Sweep**：全篇一致性回扫（术语、时态、数字格式、编号、连接）。
5. **Audit**：跑脚本，`fail` 必须修到无 critical；`review` 逐条处理或标注。
6. **Package**：写完整改文、changes、audit、result.json；按平台契约落盘。

## 4. 角色分离

- **Agent**：理解文本、判断语义、写改文、解释理由。
- **脚本**：切句、抽数字/引用/限定/否定、比对守恒、检术语、算改动比例。
- **作者**：确认术语选择、事实性歧义、无法判断的改写。

脚本不替代 Agent 写作；Agent 不用心算代替脚本核验。

## 5. 验收标准

- `gate != fail`；所有 critical 已修或已明确标为无法修；
- 主产物 `polished_text` 完整覆盖原文（段落不缺）；
- `changes` 每条可回原文句，类型为 G/T/R；
- `result.json` 通过 `validate_result.py`；
- 交付物路径真实存在且非空。
