# 输入输出字段契约（Output Contract）

## 输入：polish JSON

| 字段 | 类型 | 说明 |
|-|-|-|
| `case_id` | str | 案例标识 |
| `target_register` | str | 目标语域：`journal`/`thesis`/`grant`/`rebuttal`/`abstract` |
| `source_lang` | str | 源语言：`en`/`zh`/`mixed` |
| `paragraphs` | list[dict] | 真实稿件段落：`id`/`section`/`kind`/`text` |
| `glossary` | list[dict] | 术语表：`source`/`target`/`scope` |
| `polished` | dict | 真实润色文本 `{段号: 文本}`（可选；不提供则不臆造） |

## 输出：pipeline result.json

```json
{
  "case_id": "案例标识",
  "status": "success | partial | needs_review",
  "has_polished": true,
  "result": {
    "paragraph_count": 2,
    "sentence_count": 5,
    "grammar_issues": 2,
    "term_inconsistencies": 0,
    "register_flags": 1,
    "protected_tokens": 12,
    "preservation": {"checked": true, "counts": {...}, "issue_count": 0},
    "verification": {"consistent": false, "issues": [], "needs_review": []},
    "evidence_index": [{"sentence_id":"P1_S1","para_id":"P1","protected_kinds":[...]}],
    "summary": "段/句/守护元素/守恒核验/核验问题汇总"
  }
}
```

## 端到端交付（完成器 solve / render-draft）

### 真实输入字段（solve 适配）

| 字段 | 形态 | 说明 |
|-|-|-|
| `paragraphs` | 内联 list | 直接结构化段落 |
| `source_text` | str | 纯文本，按空行/换行切段 |
| `source_files` | `[路径]` 或 `{名:路径}` | 读 `.txt/.md/.json` 真实稿件 |
| `glossary_file` | 路径 | 术语表文件（.json 或两列 TSV/CSV） |
| `polished` | `{段号: 文本}` | 内联真实润色文本 |
| `polished_files` | `{段号: 路径}` | 真实润色文本文件 |

读不到不臆造，记入 `adapter_notes` 并交缺口清单。

### 输出：solve result.json

```json
{
  "case_id": "e2e-demo",
  "status": "partial",
  "input_mode": "case",
  "source_count": 2,
  "adapter_notes": ["source_text 切段 2"],
  "result": {
    "polished_draft": "[P1_S1] 原文: ...\n      改文: ...",
    "draft_text": "...",
    "blocks": [{"id":"P1_S1","source":"...","target":"...","change_types":[],
                "reasons":[],"glossary_basis":[],"protected_kinds":[],"status":"needs_polish"}],
    "verification": {"consistent": false, "issues": [], "needs_review": []},
    "evidence_index": [],
    "summary": "..."
  },
  "needs_review": [],
  "uncertainty": [],
  "delivery": {"written": true, "path": "/app/output/result.json", "bytes": 1234}
}
```

`delivery.written=true 且 bytes>0` 才视为交付成功。

### render-draft / pipeline --with-draft

`render_draft` 产出逐句成稿草稿：`polished_text`、`blocks`、`pending_polish`、
`needs_author_confirmation`、`term_inconsistencies`、`register_flags`、
`preservation_issues`、`unverified_relations`、`uncertainty`。
无真实改文的句 `target` 为〔待润色〕，`status=needs_polish`。

## 装配正式 result.json（手工路径）

若不用 `solve`，可分别运行子命令后按上表装配；必须保留 `case_id`、主结果、
证据定位（evidence_index/blocks）、运行状态（status）、不确定性（needs_review/uncertainty）
与修改记录，缺项显式标注，不得伪造。
