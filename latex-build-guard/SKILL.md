---
name: latex-build-guard
description: LaTeX 写作与编译守门人。当任务要求编写或修复 LaTeX 工程、在指定模板下真实编译、定位报错到文件行号、处理公式表格引用与模板必填项、交付可继续编辑的 .tex 源码与编译通过的 PDF 时使用。先真实编译得到基线，按日志修复源码并反复编译直到通过，再核对产物页数与内容；编译器缺失或无法通过时如实交付 partial，不伪造 PDF 或编译成功。不适用于非 LaTeX 排版或纯文字写作。
---

# LaTeX 编译守门人（LaTeX Build Guard）

面向真实 LaTeX 工程的写作与编译技能。核心不是"给一段能看的源码"，而是**真的把工程编译通过、修对内容、交付可编辑源码与真实 PDF、留下可复现记录**。

四问与工具：

| 题面问题 | 你要做的事 | 工具 |
|---|---|---|
| 编译得通 | 真实编译得到基线，逐条修错，复编译至无 error | `compile_latex.py` + `classify-errors` |
| 改得对 | 公式/编号/表格/交叉引用/模板必填项与原文一致 | `check-content` + `check-source` |
| 交得可用 | 交付 `.tex` 工程 + 真实 PDF，不是截图/片段 | `check-deliverable` + 编译产物 |
| 复现得了 | 记录发行版、引擎、宏包、命令与轮次 | `check-reproducibility` + 编译记录 |

## 何时触发 / 不触发

**触发**：写/改 LaTeX 源码、修编译错误、模板迁移、公式表格引用处理、要求交付可编译源码或 PDF。

**不触发**：非 LaTeX 排版、纯文字写作。误触发时说明并保持原文不变。

## 铁律

1. **先编译，再修**：不许只看代码猜错。先跑 `compile_latex.py` 拿到真实日志与 PDF，再按 `file:line` 修。
2. **修源码，不是写报告**：必须实际编辑 `.tex/.bib/.cls` 文件；只输出"建议"不算完成。
3. **编译通过才算交付**：`compile_ok=true`、PDF 页数 > 0、且 `pdf_text_check.ok` 不为 `false`（`null` 表示环境无文本抽取后端，需在 `uncertainty` 说明）才能把状态写成 success；否则 partial 并说明卡在哪。
4. **不伪造产物**：编译器缺失、缺宏包、模板类文件缺失、权限不足，一律如实写进 `uncertainty`，不虚构 PDF、页数或"已编译"。
5. **改动可回溯**：每条修改记录"原源码 → 改后 → 类型 → 理由 → 文件:行号"。
6. **不交预制答案**：处理平台给定工程，不拿预写源码或样例产物冒充。

## 工具一：compile_latex.py（真实编译）

```bash
python scripts/compile_latex.py <工程目录> [--main main.tex] [--engine auto|pdflatex|xelatex|lualatex] \
  --outdir /app/output --json-out /app/output/compile_report.json
```

它会：识别主文件与引擎（magic comment / ctex / xeCJK）→ 复制到临时目录 → 用 `latexmk` 或 `pdflatex/xelatex/lualatex/tectonic` 多轮编译 → 解析 `.log`（`file:line: error`、`! ...`、`l.N`、级联）→ 抽取 PDF 文本确认不是空壳 → 复制 PDF 与可编辑源码到输出目录 → 返回 JSON：`compile_ok`、`pdf`、`pages`、`pdf_text_check`、`errors[]`、`cascading`、`missing_files[]`、`log_tail`。

**返回 `no_latex_compiler`**：说明镜像没有 TeX。此时改用静态检查链路，交付 partial，并在 `uncertainty` 写明"无法真实编译"，不得声称编译成功。

## 工具二：latex_engine.py（静态检查与日志分类）

```bash
python scripts/latex_engine.py check-source input.json
python scripts/latex_engine.py classify-errors input.json
python scripts/latex_engine.py check-content input.json
python scripts/latex_engine.py check-deliverable input.json
python scripts/latex_engine.py check-reproducibility input.json
python scripts/latex_engine.py pipeline input.json > result.json
```

`input.json` 常用字段：

```json
{
  "case_id": "案例标识",
  "main_tex": "主文件全文",
  "sub_files": {"chapter1.tex": "子文件内容"},
  "compile_log": "编译日志全文",
  "bib": "@article{key2020, ...}",
  "files": {"main.tex": "主文件内容", "refs.bib": "bib内容"},
  "build_record": "TeX Live 2023 / 模板 v1.2 / 宏包 / 字体 / 命令 / 轮次",
  "template_required_fields": ["AuthorEmail", "Abstract"],
  "required_repro": ["tex_dist","template_version","packages","fonts","compile_cmd","rounds"]
}
```

`classify-errors` 会给出 `error_count/categories/errors`（含 `file/tex_line/cause`）；`check-content` 检查悬空 `\ref/\eqref`、`\cite` 无 bib、表格列数、模板必填项；`check-deliverable` 检查是否交付 `.tex`；`check-reproducibility` 检查构建记录。

## 标准工作流（必须按顺序执行）

1. **读输入**：读 `/input/case.json` 与 `task.md`，确认 `case_id`、工程目录、主文件、目标模板、要改的章节/公式/表格/引用、输出契约字段。**逐个打开真实文件**，不从文件名猜内容。
2. **落盘副本**：把工程复制到 `/app/work/latex`，在副本上改，原始输入不动；同时先保存一份诚实基线（`git diff` 或文件副本）。**若 case.json 只给 `main_tex` 文本或 `files` 表、没有真实工程目录，先按原样把每个文件写到 `/app/work/latex/`（不增删内容、不改编码），再进入编译。**
3. **基线编译**：跑 `compile_latex.py`。记下 `compile_ok`、`errors`、`missing_files`、`pages`。这是后续对照的基线。
4. **修错**：用 `classify-errors` 对日志分类，按 `file:line` 逐条修：
   - 缺宏包/类文件：确认镜像是否已装；不可安装则改用等价宏包或移除依赖，并在记录中说明；
   - 未定义命令/花括号/环境未闭合：修源码；
   - 引用/交叉引用：补 `\label`、修 `\ref`、确保 `.bib` 条目存在；
   - 级联错误先修根因，不逐条打补丁。
   每修一轮**立即重新编译**，直到 `compile_ok=true` 或确认环境不可能通过。
5. **改内容**：跑 `check-content`，修悬空引用、`\cite` 无条目、表格列数、模板必填项；公式符号、编号、表格数值与原文核对，不擅自改原意。
6. **产物验收**：用 `check-deliverable` 确认 `.tex/.bib/子文件`齐全；核对 `compile_latex.py` 返回的 PDF 存在、`pages>0`、`pdf_bytes>0`；用 PDF 文本工具抽取首页/关键页文字，确认不是空壳或旧 PDF。
7. **复现记录**：跑 `check-reproducibility`，补齐 `tex_dist/template_version/packages/fonts/compile_cmd/rounds`；记录最终引擎与轮次。
8. **装配输出**：按 `references/output_contract.md` 写 `/app/output/result.json`，保留 `case_id` 与全部契约字段；`result` 必须含：
   - `latex_source`（主文件与子文件路径、关键改动）；
   - `compiled_pdf`（路径、页数、字节数、`compile_ok`）；
- `pdf_text_check`（`ok`、`backend`、`chars`、前 300 字符样例；无后端时给 `reason`）；
   - `compile`（引擎、轮次、错误/警告、缺失文件）；
   - `changes`（原→改→类型→理由→file:line）；
   - `summary`（一行结论）。
   同时把可编辑源码与 PDF 复制到 `/app/output/` 下的稳定路径。

## 输出契约要点

顶层：`case_id`、`status`（`success`/`partial`/`needs_review`）、`result`、`evidence`、`uncertainty`。
`result` 至少含 `latex_source`、`compiled_pdf`、`pdf_text_check`、`compile`、`changes`、`verification`（五项检查）、`summary`。
`evidence` 至少含 `error_locations`、`dangling_refs`、`template_checks`、`pdf_evidence`。
`uncertainty` 至少含 `needs_compile_verify`（仅静态检查时 true）、`missing_files`、`note`。
完整字段见 `references/output_contract.md`。

## 异常处理

| 情形 | 处置 |
|---|---|
| 无 TeX 编译器 | 返回 `no_latex_compiler`，改用静态检查，status=partial，写清无法真实编译 |
| 缺宏包/类文件 | `missing_files` 列出；能替代则替代，不能则标注并交付 partial |
| 报错级联 | `cascading=true` 先修根因；集中修同一文件相邻错误 |
| 模板版本不明 | 构建记录标 `not_reported`，按通用类尝试并标注 |
| 中文模板 | ctex/xeCJK 自动切 xelatex；字体缺失时记录并尝试 fallback |
| 编译超时 | 减少轮次或单轮 timeout；保留日志与已生成 PDF，status=partial |
| 权限不足 | 标注目录权限问题，交人工；不伪造成完成 |

## 资源

- `scripts/compile_latex.py`：真实编译闭环（latexmk/pdflatex/xelatex/lualatex/tectonic，日志定位，PDF/页数）
- `scripts/latex_engine.py`：结构/错误/内容/交付/复现五项静态检查
- `references/error_patterns.md`：错误分类与修复策略
- `references/source_rules.md`：源码结构与宏包顺序
- `references/content_checks.md`：公式/表格/引用一致性
- `references/output_contract.md`：字段契约
- `examples/minimal_example.md`、`examples/selftest.py`、`examples/testset.json`：示例与自测

## 限制与边界

- `compile_latex.py` 不安装宏包、不改系统 TeX；缺依赖时如实报错。
- 静态检查不能替代真实编译；只有 `compile_ok=true` 且 PDF 可读才可声称编译通过。
- 不联网、不伪造 PDF/页数/日志；所有结论可回到文件与行号。


## 交付前自检（必须）

```bash
python scripts/validate_result.py --result /app/output/result.json --outdir /app/output --case /input/case.json --main-field latex_source
```

`valid=false` 时按 errors 修；`result.latex_source` 为空、顶层缺 `case_id/status/result/evidence/uncertainty`、或声明的产物路径不存在，都不得声称完成。

