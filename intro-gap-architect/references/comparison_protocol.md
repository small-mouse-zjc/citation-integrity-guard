# 公平对照协议（Fair Comparison Protocol）

服务于评分表"使用增益 25 分"与"创新证据 5 分"：加载 Skill 后是否相对不加载的基础 Agent 有可验证改善。本文说明对照怎么做、度量什么、以及哪些结论必须由平台给出、不得自造。

## 对照设计

- **同一输入**：基线与 Skill 使用完全相同的固定案例——事实底稿、受众、文体、格式约束、`case_id`。
- **同一条件**：相同模型、相同请求数上限（题面 64 请求）、相同 token 预算（16k/响应）、相同超时（900 秒）。
- **基线**：不加载本 Skill，直接按任务指令写引言与相关工作。基线缺陷按题面四类常见失败建模（见下）。
- **Skill**：加载本 Skill，先跑 `intro_engine` 的确定性检查与门禁，再按 `compose` 骨架成稿并核对 `source_map`。

## 基线缺陷模型（四类常见失败）

`compare._baseline_signals` 按题面描述的失败类型构造基线会犯的错：

1. 空转铺垫未标出（"近年来受到广泛关注"式）；
2. 相关工作逐篇摘要、无统一分组维度；
3. 研究空白无支撑文献（断言式）；
4. 贡献无证据锚点或含夸大词仍照写。

这是**方法对照用的确定性基线模型**，用于证明"Skill 能检出/拦截哪些缺陷"，不是任何真实 Agent 的输出，也不是平台白板。

## Skill 侧度量（可确定性复核）

| 维度 | 基线表现 | Skill 检出/拦截 | 门禁 |
|---|---|---|---|
| 立得住 | 套话句未标出 | `hype_count` 标出无锚点套话 | `holds_up=false` 禁入下一步 |
| 分得清 | N 篇平铺为逐篇摘要 | `group_count` 个统一维度分组 + 同维比较视图 | 无法分组进 `needs_review` |
| 说得实 | 空白无支撑文献 | 每条 gap 附 `supporting_works` + `reasoning` | 零证据不生成空白 |
| 对得上 | 无锚点/夸大贡献照写 | `unbacked`/`inflated` 拦截 | `all_backed=false` 禁成稿 |

`compare.gain` 输出的 `defects_skill_detects`、`groups_added`、`claims_gated` 是**确定性计数**，任何人用相同输入重跑 `compare` 都能复现。

## 复现命令

```bash
# 单案例对照
python scripts/intro_engine.py compare examples/smoke_input.json
# 三案例 benchmark（把每个 case.input 原样喂入 compare，核对 expect 字段）
python -c "import json;d=json.load(open('examples/benchmark.json',encoding='utf-8'));print([c['case_id'] for c in d['cases']])"
```

## 边界声明（务必遵守）

- 本 Skill **不提供**质量分、效率耗时、平台白板对照结果——这些由组织方用固定案例生成（`challenge.json.scoring.strategy = human_review_only`）。
- `compare` 度量的只是"缺陷检出/拦截能力"这一可验证增益，不能替代人工评审对成稿质量、忠实度、创新价值的判断。
- 标注为示例/smoke 的输出不得冒充正式案例结果；正式测试案例与白板由平台提供。
- 效率增益（请求数/耗时/返工轮次）的实际数值由平台记录，`--compact` 只是降低中间结果 token 占用的一项设计，不宣称具体节省数字。
