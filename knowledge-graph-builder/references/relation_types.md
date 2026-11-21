# 关系类型、方向与证据强度

## 受控关系类型

| 关系 | 中文 | 方向 | 说明 |
|------|------|------|------|
| uses | 使用 | subject→object | 方法/作者使用某材料、模型、数据 |
| applies | 应用于 | subject→object | 方法应用到某任务/数据集 |
| proposes | 提出 | subject→object | 作者提出方法/结论 |
| compares | 比较 | subject↔object | 两个方法/结果的对比 |
| outperforms | 优于 | subject→object | 有条件的性能优势判断 |
| measures | 测量/评价 | subject→object | 用某指标评价 |
| supports | 支持 | subject→object | 结果支持某结论 |
| contradicts | 矛盾 | subject↔object | 结果与结论冲突 |
| reports | 报告 | subject→object | 论文报告某数值/结果 |
| derives-from | 源自 | subject→object | 方法/数据 derivations |
| evaluated-on | 在…上评估 | subject→object | 在数据集/样本上评估 |
| achieves | 达到 | subject→object | 达到某指标值 |
| correlates-with | 相关于 | subject↔object | 相关性（非因果） |

方向取值 `direction`：`forward`（有向）、`reverse`、`symmetric`（双向/无向）。共轭关系（compares/contradicts/correlates-with）应标 symmetric，不得据此声称因果或优劣方向。

## 适用条件 condition

每条关系应声明适用条件（样本、数据集、参数范围），避免把某条件下的结果泛化。缺条件 → `no_condition`（warning）。例如"方法A 优于 方法B"必须注明是在哪个数据集/样本上的结论。

## 证据强度 evidence_type

强证据（可作直接关系）：

- `direct`：论文直接陈述
- `quoted`：带引号原文
- `table` / `figure`：表格或图中明确给出

弱证据（**不得**当成直接关系，标 `weak_evidence_as_relation` error）：

- `cooccurrence`：仅在同一段落/句子共现
- `hearsay`：综述或他人转述
- `speculation`：推测、may/might/suggest
- `inference`：读者推理
- `common-knowledge`：常识补全

## 跨篇关系

跨两个 source_id 的关系必须：

1. `cross_paper: true` 显式标注（否则 `cross_paper_unmarked` error）；
2. 有强证据（弱证据 → `cross_paper_weak_evidence` error）；
3. 明确是"方法名相同"还是"同一实体"，不得把两篇的样本/条件/数值拼成一个结论。

## 端点指代

关系的 `subject` / `object` 可以写节点 `id`（如 n1）或节点 `surface`（如 CNN）；`query-graph` 解析时两种都认，确保结果子图能回到节点证据。
