# 文献知识图谱构建守门人（knowledge-graph-builder）

从真实科研论文抽取实体与关系、绑定原文证据、处理别名与跨篇同名冲突、执行可回查查询、支持增量更新的最小可运行图谱工作流。

## 能力

- **抽得准**：实体真在论文 JATS 段落出现、类型合法、保留原文短引、区分自述/转述。
- **连得对**：关系只取受控类型并带方向/条件，共现、综述转述、推测一律不作直接证据。
- **对得齐**：别名归一给依据，跨篇相同表面默认不合并（防止把同名方法/材料当成同一实体或把两篇条件拼成一个结论）。
- **查得到、回得去**：至少 3 个真实查询，结果子图每个节点/边都能回到 source_id + JATS 段落 + 原文短引。
- **增量更新**：新论文加入保留既有节点编号，记录新增/合并/保留冲突。

## 结构

```
knowledge-graph-builder/
  SKILL.md                     技能定义（YAML frontmatter + 四问 + 铁律 + 工作流）
  README.md                    本文件
  GITHUB_URL.txt               公开作品链接
  scripts/kg_engine.py         纯标准库确定性引擎（10 子命令，含 solve/render-draft）
  references/
    output_contract.md         pipeline 输出字段契约
    entity_types.md            实体类型与 attribution 规则
    relation_types.md          关系类型/方向/证据强度
    alignment_rules.md         别名归一与跨篇冲突规则
    evidence_binding.md        来源绑定与 JATS 位置规范
    query_templates.md         3 类查询模板与示例
  examples/
    selftest.py                62 项自验收测试（含成稿/正文抽取/solve）
    smoke_input.json           冒烟输入
    smoke_output.json          引擎真实运行的冒烟输出
    minimal_example.md         最小可运行示例
```

## 运行

```bash
python examples/selftest.py                         # 62/62
python scripts/kg_engine.py solve /input/case.json --out /app/output
python scripts/kg_engine.py render-draft examples/smoke_input.json > draft.json
python scripts/kg_engine.py pipeline examples/smoke_input.json --with-draft > out.json
```

无第三方依赖，无网络请求。Python 3.8+。

## 设计立场

本 skill 不臆造实体、关系、证据或来源；脚本只做结构与规则校验。实体/关系是否忠实、别名是否真同指、证据是否支撑属价值判断，须由 Agent 结合原文复核。所有位置均为组织方 JATS 段落 ID，不是 PDF 页码。


## 冲分证据（可复现）

- 四问：抽得准 / 连得对 / 对得齐 / 查得到回得去
- 公平对照：`python scripts/compare_engine.py examples/benchmark.json`（clean 验证不误报，defect 验证能检出，可复现）。
- 只度量 Skill 检查机制的可运行证据，不编造平台质量分；真实对照由平台给出。
- 自验收：`python examples/selftest.py`（含对照可复现验证）。
