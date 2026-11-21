# 可复用词表与判定口径

供 Agent 复用，避免每次重新发明判定标准。所有判定以 `scripts/latex_engine.py` 实际输出为准，词表只统一口径。

## 状态词

| 词 | 含义 | 触发条件 |
|----|------|---------|
| `ok` | 五项检查全通过 | 结构 OK + 日志无 error + 内容 OK + 交付可用 + 复现齐 |
| `needs_attention` | 有不通过项 | 五项任一不满足 |
| `partial` | 材料不足/无法真编译 | Agent 依据材料缺口判定，引擎不自动给 |

## 严重度词

- `error`：必须修复才能编译通过或满足题面（缺 document、悬空引用、cite 无 bib、表格列数不符、必填项缺失）。
- `warning`：建议修复但不阻断（不常见宏包、加载顺序、eq 命名、bib 未引用、片段源码）。

## 四类核心问题代号

- `编译得通` → `error_classification`（`classify-errors`）
- `改得对` → `content_check`（`check-content`）
- `交得可用` → `deliverable_check`（`check-deliverable`）
- `复现得了` → `reproducibility_check`（`check-reproducibility`）

## 错误 category 词表（与 error_patterns.md 一致）

`undefined_control` / `missing_file` / `missing_package` / `missing_font` / `unclosed_group` / `math_error` / `reference_undefined` / `float_overflow` / `table_error` / `package_conflict` / `permission` / `general_error` / `other`

## issue type 词表

源码：`missing_docclass` / `document_env` / `uncommon_package` / `package_order` / `missing_subfile` / `brace_unbalanced`
内容：`dangling_ref` / `eq_label` / `table_spec` / `table_col_mismatch` / `cite_no_bib` / `bib_uncited` / `template_required`
交付：`no_tex` / `binary_only` / `fragment`

## 复现项标签

`tex_dist`（TeX发行版）/ `template_version`（模板版本）/ `packages`（宏包及版本）/ `fonts`（字体依赖）/ `compile_cmd`（编译命令）/ `rounds`（编译轮次）

## 省 token 约定

长文/多案例时用 `pipeline --compact`：只回 `status` + `summary`（五项布尔）+ `problems`（待修清单）+ `needs_compile_verify`，不重复原文与完整证据。需要完整证据链时再跑非 compact 版。
