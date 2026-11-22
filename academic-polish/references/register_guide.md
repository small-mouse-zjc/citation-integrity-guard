# 语域指南（check_register）

按 `target_register` 选择语气标准，诊断四类偏离：

| 载体 | 口语化 | 绝对化 | 宣传化 | 人称 |
|-|-|-|-|-|
| journal（期刊） | 忌 | 忌 | 忌 | 谨慎 |
| abstract（摘要） | 忌 | 忌 | 忌 | 忌第一人称 |
| thesis（学位） | 忌 | 忌 | 忌 | 允许适度 |
| grant（基金） | 控制 | 控制 | 控制 | 允许 |
| rebuttal（回复） | 控制 | 忌 | 控制 | 允许"我们" |

诊断词表：
- 口语化：a lot of / stuff / kind of / really / very / 挺 / 其实 / 基本上 …
- 绝对化：always / never / definitely / proves / clearly / 一定 / 必然 / 显然 …
- 宣传化：revolutionary / groundbreaking / novel / state-of-the-art / 革命性 / 世界一流 …
- 人称：I / we / my / our / 我 / 我们 …

命中项进 `register_flags` 与 `needs_review`，由模型/用户结合载体判断，不自动改写。
