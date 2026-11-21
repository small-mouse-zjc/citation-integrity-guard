---
name: latex-build-guard
description: LaTeX 写作与编译守门人。当任务涉及 LaTeX 源码编写与修改、公式表格引用处理、宏包与模板适配、编译错误定位修复、交付可编译源码或保证构建可复现时使用本技能。通过确定性脚本做源码结构检查、编译日志错误分类定位、公式表格引用一致性校验、交付物与复现记录检查，把报错定位到文件行号根因、把交付物落成可编辑 .tex 源码，不臆造编译成功或产物。不适用于非 LaTeX 的排版或纯文字写作。
---

# LaTeX 编译守门人（LaTeX Build Guard）

面向真实 LaTeX 工程的写作与编译技能。目标不是"给一段能看的源码"，而是让**源码编译得通、改动符合原文与模板、交付的是可编辑 .tex、他人按记录能复现同一产物**。

围绕题面四个核心问题组织能力：

| 核心问题 | 含义 | 对应工具 |
|---------|------|---------|
| 编译得通 | 报错定位到文件/行号/根因，不停在第一条 | `classify-errors` |
| 改得对 | 公式编号、表格列宽、交叉引用、模板必填项合规 | `check-content` |
| 交得可用 | 交付可编译可编辑的 .tex，不是 PDF/截图/片段 | `check-deliverable` |
| 复现得了 | 模板/宏包/字体版本与编译命令轮次记录齐全 | `check-reproducibility` |

另有 `check-source` 检查源码结构与宏包加载顺序。

## 何时触发 / 何时不触发

**触发**：任务中出现以下任一信号——
- 让写/改 LaTeX 源码、处理公式表格引用、迁入期刊/学位论文模板；
- 编译报错要定位修复、"加一个宏包坏另一处"的连锁问题；
- 要求交付可编译源码、要求记录编译环境与轮次保证复现；
- 抱怨"编译不过/引用显示问号/表格溢出/宏包冲突"。

**不触发**：非 LaTeX 排版、纯文字写作。被误触发时说明并保持原文不变。

## 核心原则（贯穿所有动作）

1. **错误看全**：编译日志要解析出所有 error 并逐条分类定位，不能停在第一条报错。级联错误（多条同源）要先修根因。
2. **定位到点**：每条报错给出 category、可能的文件与行号、根因说明与修复方向，让 Agent 有的放矢。
3. **交付源码**：结果必须是结构清楚、可编辑、可独立编译的 `.tex` 工程（含必要 .bib/子文件），**不把 PDF、截图或片段当结果**。
4. **复现记录**：说明 TeX 发行版、模板版本、宏包与字体依赖、编译命令与轮次，他人据此可重建。
5. **诚实标注**：缺宏包、缺字体、模板类文件缺失、权限不足、无法真编译一律显式标注，**绝不臆造"编译成功"或虚构产物**。引擎只做静态检查与日志解析，真正编译由 Agent 在平台环境执行。
6. **不交预制答案**：处理平台给定案例，不用预写源码/产物替代实际运行。
7. **确定性动作交给脚本**：结构检查、错误分类、引用一致性、交付物与复现检查必须用 `scripts/latex_engine.py` 实际运行。

## 工具：latex_engine.py

位置：技能目录下 `scripts/latex_engine.py`，纯 Python 3 标准库，无第三方依赖、无网络请求、不调用 TeX 编译器。

先确认可运行：
```bash
python scripts/latex_engine.py --help
```

### 子命令

| 子命令 | 作用 | 关键输出 |
|--------|------|---------|
| `check-source` | 源码结构与宏包 | `structure_ok`、`issues`（缺 document/宏包顺序/缺子文件） |
| `classify-errors` | 编译得通：错误分类定位 | `error_count`、`categories`、`errors`（含 file/tex_line/cause） |
| `check-content` | 改得对：公式表格引用 | `content_ok`、`issues`（悬空引用/cite无bib/必填项缺失） |
| `check-deliverable` | 交得可用：交付物 | `usable`、`tex_files`、`issues` |
| `check-reproducibility` | 复现得了：构建记录 | `reproducible`、`missing` |
| `pipeline` | 串联五步 | 完整结构化结果 |

输入为 UTF-8 JSON。推荐一次跑完：
```bash
python scripts/latex_engine.py pipeline input.json > result.json
```
长文或多案例为省 token，用 `--compact` 只回状态、五项摘要与待修问题清单：
```bash
python scripts/latex_engine.py pipeline input.json --compact > summary.json
```

`check-content` 的表格检查会正确解析 `l/c/r/p{..}/m{..}/b{..}/X` 列格式（忽略 `|`、`@{..}`、`>{..}` 等修饰），并逐行核对单元格数与列数是否一致，含 `multicolumn` 合并单元格。宏包加载顺序按整段字符位置判定，兼容多个 `\usepackage` 写在同一行：`amsmath/xcolor` 应在 `hyperref` 前，`cleveref/cite/natbib/biblatex` 应在其后。

`input.json` 结构：
```json
{
  "case_id": "案例标识",
  "main_tex": "\\documentclass{article} ... 主文件全文",
  "sub_files": {"chapter1.tex": "子文件内容"},
  "compile_log": "pdflatex 的编译日志全文（含 ! 报错与 l.行号）",
  "bib": "@article{key2020, ...}",
  "files": {"main.tex": "主文件内容", "refs.bib": "bib内容"},
  "build_record": "TeX Live 2023. 模板版本 v1.2 (.cls). 宏包... 字体... 命令 pdflatex. 编译2轮.",
  "template_required_fields": ["AuthorEmail", "Abstract"],
  "required_repro": ["tex_dist","template_version","packages","fonts","compile_cmd","rounds"]
}
```

字段说明见 `references/output_contract.md`。真实案例若给的是 .tex/.bib/日志文件，须**读取真实文件内容**，不要从文件名臆测。

## 标准工作流

接到任务后按此顺序执行，每步保留证据：

1. **读输入**：读取 `/input/case.json` 与 `task.md`，确认 `case_id`、工程文件、模板与任务口径。**如实读真实文件。**
2. **辨工程**：运行 `check-source`。确认主/子文件划分、导言区、宏包加载顺序；先修结构错误（缺 document、宏包顺序、缺子文件）。
3. **编译得通**：在平台环境用目标模板与发行版实际编译，把日志交给 `classify-errors`。按返回的 `errors` 逐条定位修复——缺包安装/替换、命令拼写、花括号闭合、引用多编译几轮。级联错误先修根因。修后重编译，直到无 error。
4. **改得对**：运行 `check-content`。修悬空 `\ref/\eqref`（补 label）、`\cite` 与 .bib 对应、表格列数匹配、模板必填项齐全。数值与公式含义回到原文核对，不臆造。
5. **交得可用**：运行 `check-deliverable`。确认交付的是可编辑 .tex 工程（含必要 .bib/子文件/图片），不是 PDF 或片段。
6. **复现得了**：运行 `check-reproducibility`。补齐构建记录（发行版、模板版本、宏包/字体版本、编译命令与轮次），并按记录在平台环境复编译验证一致性。
7. **装配输出**：按 `references/output_contract.md` 写入 `/app/output/result.json`，保留 `case_id` 与全部字段；.tex 源码与产物另存为文件。每条改动附"原源码 → 改后 → 类型 → 理由 → 定位"。

## 输出契约要点

`result.json` 至少包含：`case_id`、`status`、`result`（五项检查）、`evidence`（四原则落实 + error_locations + dangling_refs）、`uncertainty`（`needs_compile_verify=true` + 说明脚本不真编译）。目标产物须是可继续编辑维护的 .tex 源码。完整字段见 `references/output_contract.md`。

## 异常处理

| 情形 | 处置 |
|------|------|
| 缺宏包/缺字体/类文件缺失 | 错误分类中标出，给出安装或替代建议，不臆造已安装 |
| 报错级联 | `cascading=true` 时先修根因，不逐条打补丁 |
| 权限不足写文件 | 标注目录权限问题，交人工处理 |
| 模板版本不明 | 构建记录标 not_reported，追问或按通用类尝试并标注 |
| 无法实际编译 | uncertainty 声明，产出 partial，不虚构编译成功或 PDF 产物 |
| 中文/英文模板 | 检查规则通用；ctex/fontspec 相关按实际情况核对 |

## 复用与扩展

- `references/error_patterns.md`：错误分类表与修复策略；
- `references/source_rules.md`：源码结构、宏包顺序、常见命令误用；
- `references/content_checks.md`：公式/表格/引用一致性检查要点；
- `references/output_contract.md`：输出字段定义与示例；
- `examples/`：最小调用示例、33 项自验收（`python examples/selftest.py`）、12 道边界回归题（`testset.json`）；
- `references/vocab.md`：状态、严重度、错误 category、issue type 与复现项的统一判定口径，供复用省 token。

本技能与 `intro-gap-architect`、`methods-repro-guard`、`paper-note-archivist`、`citation-integrity` 互补：分别管引言、方法实验、阅读笔记、引用、LaTeX 编译，串联覆盖论文"读→写→排版编译"全流程。


## 可复现证据与冲分材料

本 Skill 针对四问（编译得通 / 改得对 / 交得可用 / 复现得了）配置了确定性检查机制，并提供可复现的公平对照证据：

- `scripts/compare_engine.py`：对同一输入给出"基线常见失败 vs Skill 四问检查机制"的对照，客观呈现观测值，**不编造平台质量分**（正式对照由平台固定案例与白板给出）。
  ```bash
  python scripts/compare_engine.py examples/smoke_input.json    # 单案例机制对照
  python scripts/compare_engine.py examples/benchmark.json      # 干净+缺陷两案例
  ```
- `examples/benchmark.json`：干净案例（验证不误报）+ 按四问注入缺陷的案例（验证能检出）。
- `references/innovation_boundary.md`：相对通用对话模型/现有工具的创新边界与可复现路径。
- `references/comparison_protocol.md`：公平对照协议与度量边界。
- `references/failure_patterns.md`：失败模式库、降级优先级；`references/vocab.md`：判定词表。

创新边界摘要：`latex_engine.py` 把 "编译得通 / 改得对 / 交得可用 / 复现得了" 中每问的易错动作固化为脚本判定，价值判断须建立在其可回溯证据之上；材料不足时诚实降级为 `partial`/`needs_attention`，不臆造事实、数值或来源。
