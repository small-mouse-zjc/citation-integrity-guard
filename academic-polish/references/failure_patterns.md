# 常见失败模式与对照

| 失败模式 | 朴素 Agent 表现 | Skill 机制 |
|-|-|-|
| 整段重写掩盖错误 | 换了说法但硬错误仍在 | `detect_grammar` 定位原文硬错误并给理由 |
| 术语跨章漂移 | 同一概念多种写法 | `check_terms` 全篇一致性回扫 |
| 限定强度被加强 | 删掉 approximately/可能 | `check_preserve` hedge_weakened 告警 |
| 偷偷绝对化 | 新增 proves/一定 | claim_strengthened 告警 |
| 引用编号被改 | `[1]` 变 `[2]` 或丢失 | protected_lost/added 告警 |
| 图表指向错位 | Fig. 2 变 Fig. 3 | refmark 守护 |
| 否定丢失反转原意 | "无显著差异"→"有差异" | negation_lost 告警 |
| 无法逐句说明 | 只给润色后文本 | `render_draft` 逐句原文-改文-类型-理由 |

对照只呈现机制可运行证据与成稿结构，不编造质量分；平台白板给出正式质量对照。
