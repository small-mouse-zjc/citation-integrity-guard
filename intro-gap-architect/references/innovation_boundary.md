# 创新边界：相对已有方案的不可替代性

评分表"创新增益 15 分"要求证明：新增能力/方法改进相对"通用对话模型、文献管理工具的综述草稿功能等"的边界与价值。本文给出可核对的边界论证，避免空泛宣称。

## 1. 为什么通用对话模型难以稳定做到

通用大模型可以在一次对话里"写出"一段看起来像引言的文字，但题面四问要求的不是"像"，而是"可核验地成立"。以下能力是通用模型在不借助外部确定性计算时**难以稳定复现**的：

| 四问要求 | 通用模型的典型失败 | 本 Skill 的确定性保证 |
|---|---|---|
| 立得住：套话句不得无锚点 | 套话句与同段的具体句混在一起时被"整体洗白"，注意力看不出哪句空转 | `detect-hype` 按句切分，每句独立判锚点；套话句无锚点即 `hype_count++`，`holds_up=false` 禁止进入下一步 |
| 分得清：同维度横向比较 | 逐篇摘要拼接成"流水账"，看似完整但无比较维度 | `group-matrix` 强制输出 `comparison[维度][{id,value}]` 横向视图，无法分组者进 `needs_review` |
| 说得实：空白由已引缺口推出 | 从常识"编"出一个看似合理的空白，不挂支撑文献 | `derive-gap` 每类空白必须 `supporting_works`（输入中的真实 id）+ `reasoning`；零证据则 `gap_count=0` 不生成空白 |
| 对得上：贡献与证据逐条对应 | 贡献段写"首个/SOTA"但正文无对应图表，或引用锚点指向不存在的图 | `align-claims` 检出悬空（锚点不在 `evidence_index`）与夸大（强断言词+锚点<2），`all_backed=false` 禁止成稿 |

关键差异：**这些是门禁（gate）而非建议**。通用模型会把"建议核对"写在提示里但仍可能跳过；本 Skill 把易错动作固化为脚本返回的结构化判定，模型价值判断必须建立在这些判定之上。

## 2. 相对文献管理工具综述草稿功能的边界

文献管理工具（如带 AI 综述功能的文献软件）擅长"基于库的摘要生成"，但不保证：

- **空白→贡献的可解释桥接**：`gap_to_contribution` 检查每条空白是否被本文贡献覆盖（`bridged`），工具通常不追踪这条链。
- **贡献—图表锚点的可核验映射**：`evidence_index` + `align-claims` 让"每条贡献回到具体图表/实验"成为可计算检查，而非人工通读。
- **失败模式的结构化暴露**：`needs_review` / `uncertainty` 把"不能判断"显式化，而不是用流畅文字掩盖材料缺口。
- **外部格式无损接入**：`ingest` 把 BibTeX/RIS/行式文本解析为 works 并立即跑元数据完整检查，缺字段留空不臆造。

## 3. 方法改进的实质（非提示词堆砌）

1. **写作与核对分离**：先用 `intro_engine` 完成确定性检查与门禁，再由 Agent 做价值判断，最后 `compose` 装配骨架。避免"一边写一边心算核对"导致的自我一致性错觉。
2. **按句而非按行检测**：套话句不会被同段的具体句洗白（这是从对照案例 bench-geochem / bench-medical-imaging 暴露并修复的真实缺陷，见 benchmark.json）。
3. **反例门禁**：`needs_review`、`all_backed`、`holds_up`、`gap_count>0` 四类反例优先于"看起来完整"，确保材料不足时诚实降级为 `partial`/`needs_attention`，不伪造。
4. **省额度模式**：`pipeline --compact` 只回 `status + summary + needs_review`，把 64 请求/900 秒/16k token 的预算留给价值判断与成稿，而非重复读取冗长中间结果。

## 4. 创新证据的可复现路径

```bash
# 1) 同一输入跑四问检查
python scripts/intro_engine.py pipeline examples/smoke_input.json > result.json
# 2) 跑公平对照，得到"基线会犯的缺陷 vs Skill 检出/拦截"的确定性计数
python scripts/intro_engine.py compare examples/smoke_input.json > comparison.json
# 3) 复现三个跨案例 benchmark 的增益
#    examples/benchmark.json 每个 case.input 原样喂给 compare 即可
```

`compare.gain` 只提供缺陷检出/拦截计数的确定性证据，不编造平台质量分数；正式质量与效率对照由组织方固定案例和白板给出。边界声明：本 Skill 不替代领域专家对"转述是否忠实、空白是否真成立、元数据是否真实"的价值判断，`compose` 输出的成稿骨架必须经 Agent 依 `source_map` 填写并核对。
