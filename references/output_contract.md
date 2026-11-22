# 输出契约（output_contract）

本技能每个案例返回一个结构化结果，写入平台指定的输出位置（默认 `/app/output/result.json`；可编辑产物另存为文件）。所有字段可追溯到输入，禁止编造。

## 顶层结构

```json
{
  "case_id": "案例标识（来自输入）",
  "status": "success | partial | needs_review",
  "pipeline": { "normalize": {}, "renumber": {}, "format": {}, "verify": {} },
  "result": {
    "bibliography": ["[1] ...", "[2] ..."],
    "number_mapping": {"wang2020": 1, "zhang2019": 2},
    "consistency": {"consistent": true, "problems": []},
    "evidence": {
      "dedup_decisions": [],
      "dedup_issues": [],
      "unresolved_citations": []
    }
  }
}
```

`pipeline.pipeline` 由 `citation_engine.py pipeline` 原样产出，`result` 是面向评审的精简视图。两者都保留，便于评审查看完整中间过程。

## 必含内容（对照题目交付要求）

题目要求的三类内容必须出现，缺项即为不完整：

### 1. 目标产物
- `result.bibliography`：可编辑的文后参考文献表（GB/T 7714 顺序编码制）。
- 可编辑稿件：正文引用编号已按 `number_mapping` 同步更新，另存为文件（如 `/app/output/manuscript_updated.md`），并在结果中给出文件路径字段 `artifacts.manuscript`。

### 2. 事实与来源映射
- `result.evidence.dedup_decisions`：每条合并的判据、置信度、证据（可回溯到文献库记录）。
- `result.evidence.unresolved_citations`：正文无法解析的引用点（行号 + 原 token）。
- 每条引用点建议附 `claim_source_map` 数组：`{"line": 12, "claim": "...", "ref": 3, "match": "supported|partial|mismatch|unverified", "note": "..."}`，用于逐句说明论断与文献是否匹配。
- 原则：不新增材料外事实；数字、术语、图表指向保留来源定位。

### 3. 版本与边界
- `status` 诚实取值：
  - `success`：全部处理完成，核验一致，无待核项。
  - `partial`：部分完成，存在字段缺失、未解析引用或一致性问题，`consistency.problems` 或 `evidence.dedup_issues` 有内容。
  - `needs_review`：存在需要人工确认的判断（如疑似版本重复、论断与文献主题不符），列在待核清单。
- `uncertainty` 数组：`{"item": "...", "reason": "...", "location": "...", "suggested_action": "..."}`。
- `changes` 数组：每条改动 `{"type": "dedup|renumber|format|insert|remove", "before": "...", "after": "...", "reason": "...", "evidence": "..."}`。

## 运行状态字段

`status` 之外，`pipeline.*.status` 各阶段独立记录成功/部分/待核，便于定位问题发生在哪一步。

## 装配注意

- `case_id` 必须与输入一致，不得省略。
- JSON 用 UTF-8，中文不转义（`ensure_ascii=False`）。
- 脚本已输出大部分字段；`claim_source_map`、`uncertainty`、`changes` 由 Agent 结合模型判断补充，但每条必须给出可回溯依据。
- 可编辑产物（稿件、文献表）若以 Office/PDF 提供，需同时保留真实渲染预览，且不得编造缺失软件状态或科学数据。

## 最小示例

见 `examples/minimal_example.md` 与 `examples/smoke_input.json` / `smoke_output.json`（示例输出已标注为示例，非正式案例结果）。


## 端到端交付（完成器 solve / render-draft）

### 真实输入字段（solve 适配）

`solve case.json --out /app/output` 读取 case.json，支持以下真实输入字段（读不到不臆造，记入 `adapter_notes`）：

- `manuscript` / `manuscript_file`：内联稿件或真实 `.md`/`.txt`/`.tex` 文件路径。
- `entries` / `entries_file`：内联文献条目或真实 JSON（条目数组或 `{entries:[...]}`）。
- `bib_file` / `bibliography_file`：真实 BibTeX/RIS/CNKI 文件，复用 `ingest` 自动解析。
- `checks`：`place`/`claims`/`compare_before` 可选检查开关。

### 输出：solve result.json

```json
{
  "case_id": "...",
  "status": "success | partial | needs_review",
  "input_mode": "case",
  "entry_count": 4,
  "adapter_notes": ["读取manuscript:ms.md", "文献库解析:refs.bib=2条"],
  "result": {
    "draft_text": "# 引用定稿稿件（可编辑）\n## 改写后正文...\n## 文后参考文献表...\n## 编号映射（旧→新）...\n# 待确认清单...",
    "edited_manuscript": "仅替换引用标记后的可编辑正文",
    "bibliography": ["[1] ...", "[2] ..."],
    "number_mapping": {"wang2020": 1, "zhang2019": 2},
    "cited_numbers": [1, 2],
    "uncited_entries": [],
    "consistency": {...}, "citation_placement": {...}, "claim_check": {...},
    "input_quality": {"empty_input": false},
    "summary": "去重：4→3 条（合并 1）；编号：3 条，悬空 0、未引 0、连续=是；一致性：通过"
  },
  "needs_review": ["缺引论断句 N 处须补来源", "未在正文引用的条目 N 条须确认是否保留"],
  "uncertainty": ["正文仅替换引用标记、不改措辞；未引条目显式标注，不伪装成正文引用"],
  "delivery": {"written":true,"path":"/app/output/result.json","bytes":4120}
}
```

- `result.draft_text`：可编辑定稿稿件：改写后正文 + 文后表 + 编号映射 + 待确认清单；**未在正文引用的条目显式标〔未引：正文未出现，须确认是否保留〕，不伪装成正文引用**（避免把文献库全量条目塞进文后表）。
- `result.edited_manuscript`：仅替换引用标记、不改措辞的真实改写正文。
- `result.bibliography` / `number_mapping`：按新编号排序的文后表与旧→新编号映射。
- `result.uncited_entries` / `cited_numbers`：正文未引/已引的编号，用于诚实标注与待确认。
- `status`：聚合去重/编号/核验结论；空输入（无正文且无条目）不得报 success。
- `delivery`：落盘回执；`written=true` 且 `bytes>0` 才算交付成功。异常不静默吞错，写入 `input_error` 或显式降级。

### render-draft / pipeline --with-draft

`render-draft input.json` 与 `pipeline input.json --with-draft` 在输出中给出 `draft_detail`（含 `draft_text`/`edited_manuscript`/`bibliography`/`uncited_entries`/`needs_author_confirmation`）；默认 `pipeline` 与 `--compact` 不含成稿。三者都不臆造引用，未引条目显式标注。
