# 最小调用示例（示意，非真实案例结果）

下面用一份 LaTeX 工程演示完整流程。**示意输出不是平台正式案例结果**，真实任务须读取 `/input/case.json` 与真实 .tex/.bib/日志。

## 输入 input.json

```json
{
  "case_id": "demo-latex",
  "main_tex": "\\documentclass{article}\n\\usepackage{amsmath}\n\\begin{document}\nEq \\eqref{eq:1}.\n\\begin{equation}\\label{eq:1}E=mc^2\\end{equation}\nCite \\cite{smith2020}.\n\\end{document}",
  "bib": "@article{smith2020, title={A}, author={Smith}, year={2020}}",
  "files": {
    "main.tex": "(同上 main_tex)",
    "refs.bib": "(同上 bib)"
  },
  "compile_log": "! Undefined control sequence.\nl.5 \\fooo{x}\n! LaTeX Error: File `stix.sty' not found.",
  "build_record": "TeX Live 2023. 模板版本 v1.2 (.cls). 宏包 amsmath 2022. 字体 Times. 命令 pdflatex. 编译2轮.",
  "template_required_fields": ["Abstract"]
}
```

## 调用

```bash
python scripts/latex_engine.py pipeline input.json > result.json
```

## 示意输出（节选，非真实结果）

```json
{
  "case_id": "demo-latex",
  "status": "needs_attention",
  "result": {
    "source_check": {"structure_ok": true},
    "error_classification": {
      "error_count": 2,
      "categories": {"undefined_control": 1, "missing_file": 1}
    },
    "content_check": {"content_ok": false},
    "deliverable_check": {"usable": true},
    "reproducibility_check": {"reproducible": true}
  },
  "evidence": {
    "error_locations": [
      {"category": "undefined_control", "file": "", "tex_line": 5},
      {"category": "missing_file", "file": "stix.sty", "tex_line": null}
    ],
    "dangling_refs": []
  },
  "uncertainty": {
    "needs_compile_verify": true,
    "note": "引擎不实际编译，须在平台环境修复后重新编译验证"
  }
}
```

## Agent 后续要做的事

脚本只给结构化结果，Agent 须：
1. 按 `error_locations` 逐条修复：`\fooo` 拼写/宏包、`stix.sty` 安装或替换；
2. 重编译，把新日志再跑 `classify-errors`，直到 error_count=0；
3. 修 `content_check` 的 issues（如 Abstract 必填项）；
4. 确认交付的是可编辑 .tex 工程；
5. 按 `build_record` 在平台环境复编译，验证产物一致；
6. 装配 .tex 源码 + `result.json`，每条改动附定位。
