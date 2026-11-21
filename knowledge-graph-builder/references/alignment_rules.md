# 别名归一与跨篇冲突规则

## 目标

同一对象在论文中的别名、缩写、大小写、全称简称要正确归一，既不产生重复节点，也不把不同对象错误合并。**有限合并、保守优先**：不确定时保留为两个节点并标冲突，好过错误合并。

## alias_rules 结构

```json
{"canonical": "CNN", "aliases": ["卷积神经网络", "ConvNet", "cnn"], "source_ids": ["P1"]}
```

- `canonical`：归一后的标准名。
- `aliases`：视为同指的其它表面形式。
- `source_ids`：规则适用的论文；省略表示不限定。

归一比对用 `_norm_loose`：小写、去空白、去连字符/下划线/括号。

## 合并判定

### 允许合并

- **同篇别名**：同一 source_id 内，surface 归一相同，或命中别名规则 → 合并，`basis = alias_rule` 或 `same_paper_normalized`；`canonical_of` 记录每个成员归到哪个标准名。
- **跨篇显式同指**：别名规则 `source_ids` 显式覆盖两篇且类型一致 → 可合并。这要求作者确实声明了同一对象（例如同一数据集的规范名），不是仅凭字面相同。

### 保留冲突（禁止合并）

- **跨篇相同表面**：两篇出现相同 surface（如都叫 "CNN"），无规则明确声明同指 → `cross_paper_same_surface` 冲突，保留为不同节点。原因写进 conflicts："相同通用术语不代表两篇用了相同样品/模型/数据集/条件"。
- **同名不同类型**：surface 相同但 type 不同（method vs model）→ `type_conflict`，保留为不同节点。
- **规则限定来源**：别名规则只覆盖 P1，但候选来自 P1+P2 → 仍不合并。

## 为什么不强行合并

题面明确：不能强迫每个别名都合并，也不能把不同论文的条件、样本和数值结果合成一个结论。相同通用方法/材料术语不代表两篇用了相同物理样品、模型实例、数据集或实验条件。因此本引擎在分组时先用 canonical 归组，再对跨篇组做保守判定——默认拆开，只有显式证据才合。

## 增量更新中的对齐

`incremental-update` 复用同一逻辑：

- 新节点与既有节点同篇同表面/命中别名规则 → `merged_nodes`（保留既有 id 与编号）。
- 跨篇相同表面 → `kept_conflicts`（作为独立新节点加入，分配新编号）。
- 新边端点不存在 → `skipped_edges`（dangling_endpoint）。
- `existing_node_ids_preserved` 必须为 true：既有节点编号不变。

## 生态复用

`references/assertion_samples.md`（ nanopub 作品）与本文的冲突判定思路一致，可跨作品复用同一套"保守合并 + 显式依据"经验。
