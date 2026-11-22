# 输出契约（output_contract）

每个案例返回结构化结果 `result.json`，保留输入标识、主结果、证据定位、运行状态与不确定性。

## 顶层字段

| 字段 | 类型 | 要求 |
|------|------|------|
| `case_id` | string | 与输入一致 |
| `status` | string | `ok` / `needs_attention` / `partial` |
| `result` | object | 五项结构化检查 |
| `evidence` | object | 四原则落实 + error_locations + dangling_refs |
| `uncertainty` | object | needs_compile_verify + 说明 |

## result 子字段（pipeline 产出）

| 字段 | 来源子命令 | 关键内容 |
|------|-----------|---------|
| `source_check` | check-source | `structure_ok`、`issues` |
| `error_classification` | classify-errors | `error_count`、`categories`、`errors` |
| `content_check` | check-content | `content_ok`、`issues` |
| `deliverable_check` | check-deliverable | `usable`、`tex_files` |
| `reproducibility_check` | check-reproducibility | `reproducible`、`missing` |

## evidence 子字段

- `principles`：编译得通/改得对/交得可用/复现得了 落实说明；
- `error_locations`：每条 error 的 category + file + tex_line；
- `dangling_refs`：悬空引用 label 列表。

## uncertainty 子字段

- `needs_compile_verify`：恒为 true——引擎不实际编译，须 Agent 在平台环境验证；
- `note`：说明脚本只做静态检查与日志解析，不臆造编译成功或产物。

## status 判定（引擎）

`ok`：源码结构 OK + 日志无 error + 内容 OK + 交付可用 + 复现记录齐；否则 `needs_attention`。无法实际编译或材料缺失用 `partial`。

## 目标产物要求

- 可编辑、结构清楚、可独立编译的 `.tex` 工程（含必要 .bib/子文件/图片）；
- 不把 PDF/截图/片段当结果；
- 源码改动、编译过程、产物可独立复核。

## 可编辑产物

.tex 源码与编译产物另存为文件，路径写入 result。平台要求 PDF/PNG 预览时提供真实渲染文件（由实际编译生成），不得伪造。

## 最小示例（示意，非真实案例输出）

```json
{
  "case_id": "example-01",
  "status": "needs_attention",
  "result": {
    "source_check": {"structure_ok": true},
    "error_classification": {"error_count": 1, "categories": {"missing_package": 1}},
    "content_check": {"content_ok": false, "issues": [{"type":"dangling_ref"}]},
    "deliverable_check": {"usable": true},
    "reproducibility_check": {"reproducible": false, "missing": [{"label":"字体依赖"}]}
  },
  "evidence": {
    "error_locations": [{"category":"missing_package","file":"main.sty","tex_line":null}],
    "dangling_refs": ["fig:2"]
  },
  "uncertainty": {"needs_compile_verify": true, "note": "须在平台环境实际编译验证"}
}
```


## 端到端交付（完成器 solve / render-draft）

### 真实输入字段（solve 适配）

`solve case.json --out /app/output` 读取 case.json，支持以下真实输入字段（读不到不臆造，记入 `adapter_notes`）：

- `main_tex` / `main_tex_file`：内联源码或真实 `.tex` 文件路径。
- `files`：`{文件名: 内联内容或真实路径}`；若未给 main_tex，取含 `\documentclass` 的主文件。
- `bib` / `bib_file`、`sub_files`（`{名:路径或内联}`）：真实文献库与子文件。
- `compile_log` / `compile_log_file`：真实编译日志；无日志不臆造编译成功。
- `build_record` / `build_record_file`：真实构建记录。

### 输出：solve result.json

```json
{
  "case_id": "...",
  "status": "ok | needs_attention | partial",
  "input_mode": "case",
  "source_count": 2,
  "adapter_notes": ["读取main_tex:main.tex"],
  "result": {
    "draft_text": "# LaTeX 交付包草稿（可编辑）\n### main.tex\n```latex ...```\n# 编译状态\n已提供真实编译日志：0 错误 / 0 警告\n# 待修清单\n...",
    "source_files": ["main.tex", "refs.bib"],
    "fixes": [{"where":"source","type":"...","reason":"..."}],
    "compile_status": "〔待编译验证：未提供真实 compile_log，本引擎不调用编译器、不臆造编译成功〕",
    "needs_compile_verify": true,
    "source_check": {...}, "error_classification": {...}, "content_check": {...},
    "deliverable_check": {...}, "reproducibility_check": {...},
    "summary": "源码结构通过；编译 0 错/0 警；内容通过；交付可用；复现齐全；须平台实测编译"
  },
  "needs_review": ["编译结果须由 Agent 在平台环境实测，脚本不臆造成功"],
  "uncertainty": ["源码/日志只取真实输入；无日志标〔待编译验证〕，不臆造编译成功"],
  "delivery": {"written":true,"path":"/app/output/result.json","bytes":3347}
}
```

- `result.draft_text`：可编辑 LaTeX 交付包草稿：真实源码 + 编译状态 + 逐维核验 + 待修清单；**无真实编译日志时编译状态标〔待编译验证〕，绝不声称编译成功**。
- `result.fixes`：待修清单（source/compile/content/deliverable/repro），来自真实静态检查结论。
- `result.compile_status`：如实呈现编译日志统计；无日志显式标注待编译验证。
- `status`：`ok`=源码/内容/交付/复现齐全且编译日志无错；否则 `needs_attention`/`partial`。注意 `ok` 仅表示静态检查通过，**编译是否通过仍须平台实测**。
- `delivery`：落盘回执；`written=true` 且 `bytes>0` 才算交付成功。异常不静默吞错，写入 `input_error` 或显式降级。

### render-draft / pipeline --with-draft

`render-draft input.json` 与 `pipeline input.json --with-draft` 在输出中给出 `draft_detail`（含 `draft_text`/`source_files`/`fixes`/`compile_status`/`needs_compile_verify`）；默认 `pipeline` 与 `--compact` 不含成稿。三者都不臆造编译成功。
