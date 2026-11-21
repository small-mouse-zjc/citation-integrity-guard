# nanopub-archivist · Nanopublication 构建与核验守门人

一个面向真实论文关键结论的可调用 Skill。把断言拆分、证据绑定、来源追溯、结构导出四件事，从模型的自由发挥变成可运行、可复核的确定性流程。

## 解决什么问题

Nanopublication 类任务的四个高频失败：
- **拆不细**：整段摘要塞进一个"断言"字段，无法逐条判断真假；
- **对不上**：断言找不到真正支撑它的最小证据片段，或证据位置说不出来；
- **追不回**：断言、证据、论文、作者、年份、版本之间链路断裂，他人回不到原文；
- **读不懂**：导出字段东缺西缺、序列化形态不合规，下游要人工清洗。

本 Skill 用 `scripts/nanopub_engine.py` 做确定性结构校验，给 Agent 结构化的检查结果与修复方向；断言拆分、证据忠实性、置信度判断属价值判断，留给 Agent 结合原文完成。

## 目录结构

```
nanopub-archivist/
├── SKILL.md                       # 技能主文件（平台加载，含 frontmatter）
├── README.md                      # 本文件
├── GITHUB_URL.txt                 # 公开作品链接（可选加分）
├── scripts/
│   └── nanopub_engine.py          # 纯标准库确定性引擎（6 子命令）
├── references/
│   ├── assertion_rules.md         # 原子化判据与复合句拆分
│   ├── evidence_binding.md        # 最小充分证据与锚点
│   ├── provenance_vocab.md        # 来源元数据与受控关系词表
│   ├── output_contract.md         # 输出字段定义
│   └── assertion_samples.md       # 20 条原子断言样例（可复用）
└── examples/
    ├── minimal_example.md         # 最小调用示例
    ├── selftest.py                # 23 项自验收
    ├── smoke_input.json           # 冒烟输入
    └── smoke_output.json          # 冒烟输出（引擎实际运行产物）
```

## 运行环境

- Python 3.8+，仅标准库，无第三方依赖、无网络请求、不调用外部服务。
- 验证：`python scripts/nanopub_engine.py --help`

## 快速开始

```bash
python scripts/nanopub_engine.py --help
python scripts/nanopub_engine.py check-assertion '{"text":"CNN在碳酸盐岩达到0.92准确率。"}'
python scripts/nanopub_engine.py pipeline examples/smoke_input.json > result.json
python examples/selftest.py
```

## 四个能力对应子命令

| 核心问题 | 子命令 | 产出 |
|---------|--------|------|
| 拆得细 | `check-assertion` | 关系映射、限定词、原子性、issues |
| 对得上 | `bind-evidence` | 绑定状态、锚点、词面重叠、issues |
| 追得回 | `check-provenance` | 六项来源元数据完整性、标识符格式 |
| 读得懂 | `check-export` | 字段完整性、可序列化、issues |

另有 `check-quality`（跨断言质量）与 `pipeline`（一次跑完全流程）。

## 设计原则

- 引擎只做结构与规则校验，**不臆造断言、证据或来源**；
- 断言原子化、证据最小充分、来源六项齐全、导出字段固定；
- 价值判断（忠实性/支撑性/置信度）显式交给 Agent，脚本只给可回溯定位；
- 与 `citation-integrity`、`intro-gap-architect`、`methods-repro-guard`、`paper-note-archivist`、`latex-build-guard` 互补，串联覆盖"读→写→核验→结构化"全流程。

## 适用与限制

- 适用：从论文结论/摘要/结果段抽取可核验的原子知识单元，输出机器可读结构。
- 限制：不内置 OCR，不访问原文数据库；扫描版无文本层须先 OCR；断言忠实性与证据支撑性须 Agent 结合原文复核；不生成预制答案。

## 许可与复用

规则文档、受控词表、断言样例与题集均可复用；引用请标注来源仓库（见 GITHUB_URL.txt）。
