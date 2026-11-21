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
