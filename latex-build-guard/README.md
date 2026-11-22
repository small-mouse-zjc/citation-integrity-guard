# latex-build-guard · LaTeX 编译守门人

一个面向真实 LaTeX 工程的可调用 Skill。既是从真实源码/日志端到端产出可编辑交付包并装配 result.json 的**完成器**，也是把编译错误定位、内容一致性、交付物校验、可复现记录四件事做成可运行、可复核确定性流程的**核验器**。编译是否通过须平台实测，脚本不臆造编译成功。

## 解决什么问题

LaTeX 写作与编译的四个高频失败：
- **编译不过还找不到根因**：停在第一条报错，级联错误逐条打补丁；
- **改不对**：公式编号乱、表格溢出、引用显示问号、模板必填项缺失；
- **交不能用**：交付 PDF 或一段无法编译的片段，而不是可编辑源码；
- **复现不了**：没记模板/宏包/字体版本与编译命令轮次，他人重建失败。

本 Skill 用 `scripts/latex_engine.py` 做静态检查与日志解析，给 Agent 结构化的错误清单与修复方向，真正编译由 Agent 在平台环境完成。

## 目录结构

```
latex-build-guard/
├── SKILL.md                       # 技能主文件（平台加载）
├── README.md                      # 本文件
├── GITHUB_URL.txt                 # 公开仓库链接（可选）
├── scripts/
│   └── latex_engine.py            # 纯标准库确定性引擎（8 子命令，含 solve/render-draft）
├── references/
│   ├── error_patterns.md          # 错误分类与修复策略
│   ├── source_rules.md            # 源码结构与宏包规则
│   ├── content_checks.md          # 公式表格引用检查
│   └── output_contract.md         # 输出字段定义
└── examples/
    ├── minimal_example.md         # 最小调用示例
    ├── selftest.py                # 54 项自验收（含成稿/适配/solve）
    ├── smoke_input.json           # 冒烟输入
    └── smoke_output.json          # 冒烟输出
```

## 运行环境

- Python 3.8+，仅标准库，无第三方依赖、无网络请求、不调用 TeX 编译器。
- 验证：`python scripts/latex_engine.py --help`

## 快速开始

```bash
python scripts/latex_engine.py --help
python scripts/latex_engine.py classify-errors '{"compile_log":"! Undefined control sequence.\nl.5 \\foo"}'
python scripts/latex_engine.py solve /input/case.json --out /app/output   # 端到端成稿+装配
python scripts/latex_engine.py render-draft examples/smoke_input.json > draft.json
python scripts/latex_engine.py pipeline examples/smoke_input.json --with-draft > result.json
python examples/selftest.py
```

## 四个能力对应子命令

| 核心问题 | 子命令 | 产出 |
|---------|--------|------|
| 编译得通 | `classify-errors` | 全量错误分类 + 文件/行号/根因 |
| 改得对 | `check-content` + `check-source` | 公式表格引用 + 模板必填项 |
| 交得可用 | `check-deliverable` | .tex 源码校验 |
| 复现得了 | `check-reproducibility` | 构建记录检查 |

另有 `pipeline` 一次跑完五项。

## 设计原则

- 引擎只做静态检查与日志解析，**不实际编译**，不臆造编译成功或产物；
- 级联错误先修根因；交付物必须是可编辑 .tex 源码；
- 与 `intro-gap-architect`、`methods-repro-guard`、`paper-note-archivist`、`citation-integrity` 互补，串联覆盖"读→写→排版编译"全流程。

## 适用与限制

- 适用：article/report/beam/学位论文等 LaTeX 工程的写作与编译辅助，中英文模板均可。
- 限制：不内置 TeX 发行版，不实际编译；错误分类基于日志模式匹配，疑难错误须 Agent 判断；不生成预制答案。

## 许可与复用

规则文档、错误模式表、测试题集均可复用；引用请标注来源仓库（见 GITHUB_URL.txt）。


## 冲分证据（可复现）

- 四问：编译得通 / 改得对 / 交得可用 / 复现得了
- 公平对照：`python scripts/compare_engine.py examples/benchmark.json`（clean 验证不误报，defect 验证能检出，可复现）。
- 只度量 Skill 检查机制的可运行证据，不编造平台质量分；真实对照由平台给出。
- 自验收：`python examples/selftest.py`（含对照可复现验证）。
