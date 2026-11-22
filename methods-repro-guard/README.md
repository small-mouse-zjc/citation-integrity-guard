# methods-repro-guard · 方法与实验可复现守门人

一个面向学术论文"方法与实验"环节的可调用 Skill。把要素完整性、数值来源核验、复现清单、缺口追问四件事，从模型的自由发挥变成可运行、可复核、可回溯的确定性流程。

## 解决什么问题

方法实验章节的四个高频失败：
- **写不全**：只留能读通的主干，步骤/设置/参数/数据/对照/限制缺斤少两；
- **写不准**：为段落顺畅补造数值，或数值与配置/日志/代码对不上；
- **做不着**：复现所需的版本、环境、种子、命令、数据获取方式没给全；
- **说不住**：限制都是"存在不足"套话，缺口不说清、交作者确认。

本 Skill 用 `scripts/methods_engine.py` 把四个动作做成确定性计算，价值判断给出可回溯证据。

## 目录结构

```
methods-repro-guard/
├── SKILL.md                       # 技能主文件（平台加载）
├── README.md                      # 本文件
├── GITHUB_URL.txt                 # 公开仓库链接（可选）
├── scripts/
│   └── methods_engine.py          # 纯标准库确定性引擎（8 子命令，含 solve/render-draft）
├── references/
│   ├── element_checklist.md       # 六类要素清单
│   ├── value_provenance.md        # 数值来源核验与补造识别
│   ├── repro_template.md          # 复现清单模板与限制具体化
│   └── output_contract.md         # 输出字段定义
└── examples/
    ├── minimal_example.md         # 最小调用示例
    ├── selftest.py                # 35 项自验收（含成稿/solve/参数名对齐）
    ├── smoke_input.json           # 冒烟输入
    └── smoke_output.json          # 冒烟输出
```

## 运行环境

- Python 3.8+，仅标准库，无第三方依赖、无网络请求。
- 验证：`python scripts/methods_engine.py --help`

## 快速开始

```bash
python scripts/methods_engine.py --help
python scripts/methods_engine.py check-completeness '{"section_text":"..."}'
python scripts/methods_engine.py solve /input/case.json --out /app/output          # 端到端成稿+装配
python scripts/methods_engine.py render-draft examples/smoke_input.json > draft.json
python scripts/methods_engine.py pipeline examples/smoke_input.json --with-draft > result.json
python examples/selftest.py
```

## 四个能力对应子命令

| 核心问题 | 子命令 | 产出 |
|---------|--------|------|
| 写得全 | `check-completeness` | 六要素完整性 + 缺失清单 |
| 写得准 | `verify-values` + `build-param-table` | 数值交叉核验 + 参数来源 |
| 做得着 | `check-reproducibility` | 复现清单缺项 |
| 说得住 | `probe-gaps` | 缺口追问 + 套话限制标记 |

## 设计原则

- 确定性动作用脚本；价值判断（数值语义一致、限制成立）留给 Agent 但必须给证据定位。
- 数值无来源、材料缺口一律显式标注交作者确认，绝不补造实验条件。
- 与 `intro-gap-architect`、`citation-integrity` 互补，可串联覆盖论文前半部分。

## 适用与限制

- 适用：中英文方法与实验章节写作，可跨学科。
- 数值核验按「参数名+数值」联合定位并含中文别名映射；数值存在但参数名不符记为弱证据（弱证据不算通过）；语义等价与实验条件是否同一仍须 Agent 核对。
- `render-draft`/`solve` 只用真实字段成稿，无来源参数/数值标〔待核实〕，不补造；`solve` 自动适配材料文件（source_files/materials）并装配 result.json + delivery 回执。

## 许可与复用

规则文档、清单模板、测试题集均可复用；引用请标注来源仓库（如公开，见 GITHUB_URL.txt）。


## 冲分证据（可复现）

- 四问：写得全 / 写得准 / 做得着 / 说得住
- 公平对照：`python scripts/compare_engine.py examples/benchmark.json`（clean 验证不误报，defect 验证能检出，可复现）。
- 只度量 Skill 检查机制的可运行证据，不编造平台质量分；真实对照由平台给出。
- 自验收：`python examples/selftest.py`（含对照可复现验证）。
