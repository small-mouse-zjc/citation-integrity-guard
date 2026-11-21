# 失败模式库（Failure Patterns）

供复核者与复用者核对"本 Skill 会漏掉什么、什么情况下会失败、如何降级"。每条给出触发条件、错误行为、正确处置与对应引擎字段，便于他人复用时理解边界。

| 编号 | 失败模式 | 触发条件 | 错误行为（若不拦截） | 正确处置（引擎保证） |
|---|---|---|---|---|
| F01 | 空转铺垫洗白 | 套话句与具体句同段/同行 | 整段因具体锚点通过，套话句漏检 | `detect-hype` 按句切分逐句判；套话句无锚点计入 `hype_count`，`holds_up=false` |
| F02 | 逐篇摘要流水账 | 相关工作按文献顺序罗列 | 无比较维度，看似全实则散 | `group-matrix` 输出 `comparison[维度]` 横向视图；无法分组进 `needs_review` |
| F03 | 无据空白 | 材料缺 limitations/conclusion | 从常识编造合理但无支撑的空白 | `derive-gap` 每类空白需 `supporting_works`；零证据 `gap_count=0` 不生成 |
| F04 | 悬空贡献 | 贡献无证据锚点或锚点指向不存在图表 | 贡献段照写，评审发现图表对不上 | `align-claims` 检出 `unbacked`（含 `missing_refs`），`all_backed=false` 禁成稿 |
| F05 | 夸大断言 | "首个/唯一/SOTA"但证据锚点<2 | 审稿被指夸大适用范围 | `align-claims` 记入 `inflated`，`compose` 标 `downgrade_required` |
| F06 | 元数据缺失 | BibTeX/RIS 缺作者/年份/来源 | 引用条目字段不全被退修 | `ingest`+`coverage` 列 `missing_metadata`，缺字段留空不臆造 |
| F07 | 外部格式误解析 | 单行 BibTeX、字段值含花括号 | 解析为空或错切 | 括号配平扫描 + 两种开闭符分别解析；不支持格式返回 `status:error` |
| F08 | 跨语种失效 | 英文摘要中的套话/问题信号 | 中文正则漏检英文 | `HYPE_PATTERNS`/`CONCRETE_SIGNALS` 含英文模式（attention/however/lack 等） |
| F09 | 近期文献误判 | current_year 与实际不符 | 把旧文献当近期进展 | `coverage` 用可配置 `current_year`/`recent_years`，仅计字段齐全的年份 |
| F10 | 价值判断越界 | 脚本检出后模型直接改结论 | 转述不忠实/元数据造假 | `compose.pending_confirmation` 与 SKILL.md 明令"事实须回原文核对，不新增材料外事实" |
| F11 | 材料不足硬凑 | 文献库为空仍要写相关工作 | 编造文献填满段落 | `coverage.total=0`、`derive-gap` 进 `needs_review`、`compose` 不生成空白，状态降级 `needs_attention` |
| F12 | 中间结果烧额度 | pipeline 返回全文多次读取 | token 预算被中间 JSON 吃掉 | `pipeline --compact` 只回摘要 + 待确认项 |

## 降级优先级（与诚实标注一致）

当多类失败同时出现，按以下优先级处置，宁可降级不臆造：

1. `material insufficient`（文献库空/字段全缺） → `status: needs_attention`，不写相关工作与空白；
2. `unbacked inflated`（贡献悬空/夸大） → `all_backed=false`，不进成稿，先补证据或删断言；
3. `hype unanchored`（套话无锚点） → `holds_up=false`，先补具体脉络；
4. `needs_review`（自动分组/价值判断） → 显式列出，交 Agent 结合原文确认。

## 复用者自查

运行 `python examples/selftest.py` 应 33/33 通过；`examples/benchmark.json` 三个案例的 `expect` 应全部命中；负例（空输入）应返回 `gap_count=0`、零编造增益。若任一失败，说明资源被改动或环境不匹配，须回退到备份版本。
