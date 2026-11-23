# 实体类型与表述身份规则

## 受控实体类型

| 类型 | 中文 | 说明 | 例子 |
|------|------|------|------|
| researcher | 研究者 | 人名、作者 | Smith, A.、张三 |
| material | 材料 | 物理样品/岩性/试剂 | 碳酸盐岩薄片、页岩样本 |
| method | 方法 | 算法/流程/技术 | CNN、阈值分割、随机森林 |
| task | 任务 | 研究任务/场景 | 图像分割、岩相分类 |
| metric | 指标 | 评价指标 | 准确率、F1值 |
| conclusion | 结论 | 论文报告的结果判断 | "优于传统方法" |
| dataset | 数据集 | 数据集合 | 砂岩数据集 |
| model | 模型 | 具体模型实例/架构 | U-Net、SVM |
| phenomenon | 现象 | 观测到的地质/物理现象 | 孔隙发育 |

类型不在上表 → `bad_entity_type`。类型相同但是不同物理对象（如两篇各自的材料/模型/数据集），跨篇仍不得合并。

## 表述身份 attribution

- `self`（作者自述）：本文/我们/作者提出、报告、使用。
- `other`（他人/综述转述）：引用、文献报道、综述称、cited/review/hearsay。

实体必须显式声明其一，否则 `bad_attribution`。区分意义：转述来的实体不可当作该论文的一手贡献，关系证据强度也应相应下调。

## 落地校验（抽得准）

实体的 `surface` 必须能在 `source_id` 对应的 `paragraph_id` 原文中命中：

- 命中 → `grounded: true`
- 未命中 → `not_grounded`（warning）且 `entity_ok: false`，视为疑似凭常识补全
- `quote` 必须同段落命中 → `quote_in_source: true`，否则 `quote_mismatch`

**根标题作者归属**：根 DOI/title/authors 属于第一篇，不得套到第二篇。第二篇用它自己的 source_id 与元数据。
