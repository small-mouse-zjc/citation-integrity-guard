# 输出契约（output_contract）

## 顶层

| 字段 | 类型 | 要求 |
|---|---|---|
| `case_id` | string | 与输入一致 |
| `status` | string | `success` / `partial` / `needs_attention` |
| `result` | object | 主产物 + 逐段/逐句改动 + 审计 |
| `evidence` | object | 四问落实 + 守恒清单 + 审计路径 |
| `uncertainty` | object | 待作者确认 + 未改项 + 说明 |

## result

| 字段 | 必填 | 内容 |
|---|---|---|
| `polished_text` | 是 | 润色后的完整文本（段落空行分隔） |
| `paragraphs` | 是 | `[{id, source_ref, text, changes[]}]`，与原文段落一一对应 |
| `changes` | 是 | `[{id, type: G/T/R, source_sentence, revised_sentence, reason, source_ref}]` |
| `termbase` | 否 | 本次执行的术语表 |
| `audit` | 是 | `polish_audit.py check` 的 gate/counts/violations |
| `delivery` | 否 | `{polished_md, polished_docx, changes_json, audit_json}` 路径 |
| `artifacts` | 否 | `polish_audit check --outdir` 实际写出的 `polished.md` / `polish_audit.json` / `outdir`；路径必须存在 |
| `summary` | 是 | 一行结论：改动类型、守恒结果、剩余待确认 |

## evidence.principles

- `改得对`：硬错误/语法/搭配改了什么；
- `说得像`：语域、术语、连接如何统一；
- `没改坏`：N/C/H/T 如何核对、审计 gate；
- `讲得清`：每条改动是否有 source_ref 与理由。

## evidence.preserved

`numbers`、`citations`、`hedges`、`negations`、`terms` 的原文清单与改文核对结果。

## uncertainty

- `needs_author_confirmation`：术语选择、事实歧义、无法判断的改写；
- `not_polished`：因原文不清/缺上下文未改的句子；
- `note`：脚本只做确定性检查，措辞质量由 Agent 负责。

## status 判定

- `success`：gate=pass 或仅剩 warning，主产物完整；
- `needs_attention`：gate=review，有 major 项待确认但仍交付；
- `partial`：输入不可读/只完成部分章节/无法输出完整改文。
