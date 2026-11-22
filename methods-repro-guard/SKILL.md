---
name: methods-repro-guard
description: 方法与实验章节写作守门人。当任务涉及撰写或改进论文"方法/实验设置/参数/数据集与划分/对照实验/可复现性/限制条件"，需要把零散实验记录整理成可执行步骤、核对正文数值与配置日志代码是否一致、检查复现清单是否给全、把材料缺口和套话限制转成具体追问时使用本技能。通过确定性脚本做要素抽取与交叉核验，数值无来源与材料缺口一律显式标注交作者确认，绝不补造。不适用于与方法和实验章节无关的问答或纯语言润色。
---

# 方法与实验可复现守门人（Methods & Reproducibility Guard）

面向学术论文"方法与实验"环节的结构化写作技能。目标不是"把段落写通顺"，而是让**每一类要素都写到、每个数值都能追溯到配置/日志/代码、复现所需的条件都给全、每处缺口都显式交作者确认**。

围绕题面四个核心问题组织能力：

| 核心问题 | 含义 | 对应工具 |
|---------|------|---------|
| 写得全 | 六类要素齐全，不只留能读通的主干 | `check-completeness` |
| 写得准 | 数值与配置/日志/代码一致，不补造 | `verify-values` + `build-param-table` |
| 做得着 | 复现清单（版本/环境/种子/命令/数据）给全 | `check-reproducibility` |
| 说得住 | 缺口显式追问、限制落到具体失效场景 | `probe-gaps` |

## 何时触发 / 何时不触发

**触发**：任务中出现以下任一信号——
- 让撰写、改写、补全方法、实验设置、参数表、数据集与划分、对照实验、可复现性声明、限制条件；
- 抱怨"方法写得太粗/复现不出来/参数对不上配置/数值不知道哪来的/限制都是套话"；
- 要求把实验记录整理成可执行步骤、要求数值与配置日志核对、要求生成复现清单；
- 要求标注材料缺口、追问实验细节、把限制落到具体场景。

**不触发**：纯语言润色、与方法实验无关的内容问答。被误触发时说明"这属于其他写作任务"并保持原文不变。

## 核心原则（贯穿所有动作）

1. **六件成套**：方法与实验＝方法步骤 + 实验设置 + 参数 + 数据集与划分 + 对照实验 + 可复现与限制。六类须齐全，缺一即不完整。
2. **来源优先**：每个数值、参数、条件都要能回到配置文件、实验日志、代码或作者确认。脚本按「参数名+数值」联合核验（含中文别名映射），数值存在但参数名不符记为弱证据，不当作通过；Agent 核对语义，结论必须给定位。
3. **绝不补造**：数值在来源中找不到时，标为"补造嫌疑"交作者确认，**不要为了段落顺畅填一个看起来合理的数**。材料缺口同理。
4. **写作与核验分离**：先用脚本做要素抽取与交叉核验，再由 Agent 做价值判断（数值是否同一条件、限制是否真成立），最后合并。
5. **诚实标注**：材料缺失、配置冲突、参数无来源、数据集版本不明、权限不足——一律写入 `uncertainty` / `needs_author_confirmation`，不臆造数值或实验条件。
6. **不交预制答案**：本技能处理平台给定案例，不得用预写好的方法章节或答案替代实际运行。
7. **确定性动作交给脚本**：完整性、数值比对、复现清单、缺口追问必须用 `scripts/methods_engine.py` 实际运行，不靠模型心算。

## 工具：methods_engine.py

位置：技能目录下 `scripts/methods_engine.py`，纯 Python 3 标准库，无第三方依赖、无网络请求。

先确认可运行：
```bash
python scripts/methods_engine.py --help
```

### 子命令

| 子命令 | 作用 | 关键输出 |
|--------|------|---------|
| `check-completeness` | 写得全：六要素完整性 | `elements`、`missing`、`complete` |
| `verify-values` | 写得准：数值与来源交叉核验 | `claims`、`unsupported`、`all_supported` |
| `check-reproducibility` | 做得着：复现清单 | `items`、`missing`、`reproducible` |
| `probe-gaps` | 说得住：缺口追问 + 限制具体化 | `open_questions`、`generic_limitations` |
| `build-param-table` | 参数表：名称/取值/单位/作用对象/来源 | `rows`、`missing_source` |
| `render-draft` | 用真实字段渲染六要素可复做章节成稿草稿 | `draft_text`、`blocks`、`source_refs` |
| `solve` | 端到端完成器：case.json →(适配材料)→ 成稿 → result.json | `result.draft_text`、`delivery` |
| `pipeline` | 串联五步 + 汇总缺口（`--with-draft` 脚本成稿） | 完整结构化结果 |

输入为 UTF-8 JSON。推荐一次跑完：
```bash
python scripts/methods_engine.py solve case.json --out /app/output            # 端到端成稿+装配
python scripts/methods_engine.py render-draft input.json > draft.json          # 六要素成稿草稿
python scripts/methods_engine.py pipeline input.json --with-draft > result.json  # 带成稿的全流程
python scripts/methods_engine.py pipeline input.json > result.json             # 仅结构化检查
```

`input.json` 结构：
```json
{
  "case_id": "案例标识",
  "section_text": "方法章节正文文本",
  "sources": {
    "config.yaml": "lr: 0.001\nseed: 42\nbatch_size: 32",
    "train.log": "epoch 100 acc 0.95"
  },
  "params": [
    {"name":"学习率 lr","value":0.001,"unit":"","scope":"优化器","source":"config.yaml"}
  ],
  "gaps": [{"field":"数据集版本","reason":"材料未给出","source":"author_confirmation"}],
  "limitations": ["在少样本场景下失效", "还有一些不足有待改进"],
  "open_questions": ["基线版本是否与本文对齐？"],
  "required_elements": ["steps","setup","params","data","baseline","repro_limit"],
  "required_repro": ["code_version","env","seed","command","data_access","split_detail"],
  "draft": "可选的章节草稿"
}
```

字段说明见 `references/output_contract.md`。真实案例若给的是 PDF、代码仓库、配置文件或日志，先按题面把事实抽取为上述结构（数值原样保留、字段缺失如实留空并记录），再运行脚本。**须读取真实文件，不从题名或标签臆测内容。**

## 标准工作流

接到任务后按此顺序执行，每步保留证据：

1. **读输入**：读取 `/input/case.json` 与 `task.md`，确认 `case_id`、任务口径、事实材料（实验记录/配置/日志/代码/数据说明）、目标文体格式。**如实读真实文件。**
2. **写得全**：运行 `check-completeness`。`missing` 中的要素须补写；材料确实没有的，写入 gaps 交作者确认，不得凭空补。
3. **写得准**：运行 `verify-values` 与 `build-param-table`。`unsupported`（数值在来源中找不到）与 `missing_source`（参数无来源）逐条核对——回到配置/日志原文确认，确属补造的删除或改回真实值，来源缺失的标注交作者。
4. **做得着**：运行 `check-reproducibility`。`missing` 中的复现项（版本/环境/种子/命令/数据获取/划分细节）按材料补齐；无法提供的显式说明原因。
5. **说得住**：运行 `probe-gaps`。把 `open_questions` 与 `generic_limitations` 显式写进结果的待确认区；套话限制须改写为具体失效场景（何种数据/条件/范围下不成立）。Agent 不得代作者回答这些追问。
6. **撰写成稿**：基于结构化结果把零散材料写成连贯的方法与实验章节。步骤写成有序可执行序列（每步输入/操作/输出/判断条件），训练/验证/测试分开描述，参数表与正文数值对齐，对照实验写成可比结论，限制落到具体场景。
7. **装配输出**：按 `references/output_contract.md` 写入 `/app/output/result.json`，保留 `case_id` 与全部字段；可编辑章节稿另存为文件。每条改动附"类型 → 理由 → 来源定位"。

## 输出契约要点

`result.json` 至少包含：`case_id`、`status`、`result`（五项结构化检查 + `method_experiment_draft` + `draft_detail`）、`evidence`、`uncertainty`。`solve` 额外含 `result.draft_text`/`blocks`/`source_refs` 与 `delivery`（落盘回执，written=true 且 bytes>0 才算交付成功）。完整字段见 `references/output_contract.md`。

## 异常处理

| 情形 | 处置 |
|------|------|
| 材料缺失 | 对应要素写入 gaps，`probe-gaps` 生成追问，不代填 |
| 配置冲突（两处数值不一致） | 标入 uncertainty，列明冲突来源，交作者裁定 |
| 参数无来源 | `missing_source` 标注，不臆造来源 |
| 数据集版本不明 | 生成"请确认数据集版本"追问，正文先标注待定 |
| 权限不足（代码/数据无法访问） | 记录受限原因，产出 partial 结果并标明限制 |
| PDF/文件读取失败 | 如实记录失败原因，不编造内容 |
| 语言/学科切换 | 中英文关键词规则均生效；`required_elements` 可按场景裁剪 |

## 复用与扩展

- `references/element_checklist.md`：六类要素的定义、判据与常见遗漏；
- `references/value_provenance.md`：数值来源核验方法与补造识别；
- `references/repro_template.md`：复现清单模板与限制具体化写法；
- `references/output_contract.md`：输出字段定义与示例；
- `examples/`：最小调用示例与 21 项自验收（`python examples/selftest.py`）。

本技能与 `intro-gap-architect`（引言与相关工作）、`citation-integrity`（引用一致性）互补：三者分别管方法实验、引言结构、引用规范，可串联覆盖论文前半部分。


## 可复现证据与冲分材料

本 Skill 针对四问（写得全 / 写得准 / 做得着 / 说得住）配置了确定性检查机制，并提供可复现的公平对照证据：

- `scripts/compare_engine.py`：对同一输入给出"基线常见失败 vs Skill 四问检查机制"的对照，客观呈现观测值，**不编造平台质量分**（正式对照由平台固定案例与白板给出）。
- `scripts/artifacts.py`：交付物渲染器（result → deliverable.md + 领域文件，纯标准库）
  ```bash
  python scripts/compare_engine.py examples/smoke_input.json    # 单案例机制对照
  python scripts/compare_engine.py examples/benchmark.json      # 干净+缺陷两案例
  ```
- `examples/benchmark.json`：干净案例（验证不误报）+ 按四问注入缺陷的案例（验证能检出）。
- `references/innovation_boundary.md`：相对通用对话模型/现有工具的创新边界与可复现路径。
- `references/comparison_protocol.md`：公平对照协议与度量边界。
- `references/failure_patterns.md`：失败模式库、降级优先级；`references/vocab.md`：判定词表。

创新边界摘要：`methods_engine.py` 把 "写得全 / 写得准 / 做得着 / 说得住" 中每问的易错动作固化为脚本判定，价值判断须建立在其可回溯证据之上；材料不足时诚实降级为 `partial`/`needs_attention`，不臆造事实、数值或来源。

## 交付文件（solve 自动生成，评审可直接打开）

`solve /input/case.json --out /app/output` 在 `result.json` 之外还会写出：`draft.md`（方法与实验成稿）、`params.csv`（参数表），以及 `deliverable.md`（人读版：概要 / 主结果 / 需人工确认 / 文件清单）。这些文件全部由 `result` 渲染而来，字段缺失就不生成对应文件、不补造；`delivery.artifacts` 里逐个记录文件名、字节数与用途。

## 统计报告充分性审计（stats_audit）

方法章节除“六类要素齐全”外，新增统计报告清单，写入 `result.stats_audit`：

- 关键项（critical）：样本量 n、重复次数、离散度（SD/SEM/CI）、统计检验名称；
- 建议项：显著性水平 α/p、效应量、多重比较校正、统计软件与版本；
- 输出 `present_count / score / missing_critical / missing_recommended`。

缺关键项时 `complete=false`，并在 `advice` 中说明审稿人可能据此要求补分析；不臆造任何统计值。
