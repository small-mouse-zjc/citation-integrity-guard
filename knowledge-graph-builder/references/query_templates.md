# 查询模板与示例

`query-graph` 支持三类查询，建议每次至少执行 3 个真实查询并核对每个结果可回查（`all_traceable=true`）。

## 1. entity 查询：按表面形式找节点

```json
{"id": "Q1", "type": "entity", "surface": "CNN"}
```

返回所有 surface 命中关键词的节点。用于"某对象在哪些论文出现""图谱里有没有某材料/方法"。

## 2. neighbor 查询：看某节点的邻接子图

```json
{"id": "Q2", "type": "neighbor", "node": "n1"}
```

`node` 可写节点 id（n1）或 surface（CNN）。返回该节点的一跳关系子图。弱证据关系（cooccurrence/hearsay/speculation）进 `unresolved_edges`，不混入支撑证据。

## 3. relation 查询：按关系类型找边

```json
{"id": "Q3", "type": "relation", "relation": "compares"}
```

返回所有该类型的关系边及其两端节点。用于"哪些方法被比较过""哪些结论被支持/矛盾"。

## 答案结构要点

每个 answer 含：

- `subgraph`：`{nodes:[...], edges:[...]}`，结果子图。
- `evidence`：每条带 `kind`（node/edge）、`id`、`source_id`、`paragraph_id`、`quote`，给了 source_index 时回填 `quote_in_source`。
- `traceable`：是否所有 evidence 都能回到论文位置。
- `unresolved_edges`：证据不足、无法确定的关系 id。
- `has_answer`：是否有结果；无结果如实返回 false，不用共现凑答案。

## 示例（冒烟输入）

`examples/smoke_input.json` 定义了 P1、P2 两篇论文，4 个实体（其中 P1 与 P2 各有一个 surface=CNN 的方法——跨篇同名冲突）、2 条直接关系，3 个查询。`examples/smoke_output.json` 是引擎真实运行输出：status=ok、跨篇冲突识别为 1、3/3 查询可回查。

注意：示例中的文本是为说明接口自造的最小样本，正式评测用平台提供的真实论文原文，不得把示例当答案提交。
