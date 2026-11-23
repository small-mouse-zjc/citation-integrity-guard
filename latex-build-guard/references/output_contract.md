# 输出契约（output_contract）

每个案例返回结构化结果 `result.json`，保留输入标识、主结果、证据定位、运行状态与不确定性。

## 顶层字段

| 字段 | 类型 | 要求 |
|------|------|------|
| `case_id` | string | 与输入一致 |
| `status` | string | `success` / `partial` / `needs_review`（或 `ok`/`needs_attention` 兼容值） |
| `result` | object | 源码、真实编译、改动、五项检查 |
| `evidence` | object | 四原则落实 + error_locations + dangling_refs + pdf_evidence |
| `uncertainty` | object | needs_compile_verify + missing_files + 说明 |

## result 子字段

| 字段 | 来源 | 关键内容 |
|------|------|---------|
| `latex_source` | 交付 | 主文件/子文件路径、关键改动、是否可独立编译 |
| `compiled_pdf` | `compile_latex.py` | `path`、`pages`、`bytes`、`compile_ok` |
| `compile` | `compile_latex.py` | `engine`、`rounds`、`errors`、`warnings`、`missing_files`、`log_tail` |
| `changes` | Agent | 原源码 → 改后 → 类型 → 理由 → `file:line` |
| `source_check` | check-source | `structure_ok`、`issues` |
| `error_classification` | classify-errors | `error_count`、`categories`、`errors` |
| `content_check` | check-content | `content_ok`、`issues` |
| `deliverable_check` | check-deliverable | `usable`、`tex_files` |
| `reproducibility_check` | check-reproducibility | `reproducible`、`missing` |
| `summary` | Agent | 一行结论（是否编译通过、页数、剩余问题） |

## evidence 子字段

- `principles`：编译得通/改得对/交得可用/复现得了 落实说明；
- `error_locations`：每条 error 的 category + file + tex_line；
- `dangling_refs`：悬空引用 label 列表；
- `pdf_evidence`：PDF 页数、首尾页抽检文本、与源码章节的对应。

## uncertainty 子字段

- `needs_compile_verify`：仅在无 TeX 编译器、只做静态检查时为 true；真实编译后应为 false；
- `missing_files`：缺宏包/类文件/字体；
- `note`：说明哪些结论未验证、为何 partial。

## status 判定

- `success`：`compile_ok=true`、`pages>0`、无 error、交付 `.tex` 工程；
- `partial`：已有可编辑源码与部分产物，但存在缺依赖/无法编译/页数为空；
- `needs_review`：材料本身无法读取或需要作者裁定。

## 目标产物要求

- 可编辑、结构清楚、可独立编译的 `.tex` 工程（含必要 .bib/子文件/图片）；
- 真实编译生成的 PDF，不得用截图或旧 PDF 冒充；
- 源码改动、编译命令与轮次、错误修复过程可独立复核。

## 可编辑产物

`.tex` 源码与 PDF 另存为文件，路径写入 result。平台要求 PDF/PNG 预览时提供真实渲染文件（由 `compile_latex.py` 实际生成），不得伪造。

## 最小示例（示意，非真实案例输出）

```json
{
  "case_id": "example-01",
  "status": "success",
  "result": {
    "latex_source": {"main": "main.tex", "sub_files": ["sections/method.tex"], "editable": true},
    "compiled_pdf": {"path": "/app/output/main.pdf", "pages": 12, "bytes": 348211, "compile_ok": true},
    "compile": {"engine": "latexmk", "rounds": 3, "errors": [], "warnings": ["Overfull \\hbox"], "missing_files": []},
    "changes": [{"before": "\\ref{fig:2}", "after": "\\ref{fig:02}", "type": "dangling_ref", "reason": "label 不存在", "location": "main.tex:88"}],
    "source_check": {"structure_ok": true},
    "content_check": {"content_ok": true, "issues": []},
    "deliverable_check": {"usable": true},
    "reproducibility_check": {"reproducible": true, "missing": []},
    "summary": "编译通过；12 页；修复 1 处悬空引用"
  },
  "evidence": {
    "error_locations": [],
    "dangling_refs": [],
    "pdf_evidence": {"pages": 12, "first_page_text": "..."}
  },
  "uncertainty": {"needs_compile_verify": false, "missing_files": [], "note": "已真实编译"}
}
```
