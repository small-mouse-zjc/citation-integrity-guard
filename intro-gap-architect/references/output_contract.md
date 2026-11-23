# 输出契约（output_contract）

## 顶层

| 字段 | 类型 | 要求 |
|---|---|---|
| `case_id` | string | 与输入一致 |
| `status` | string | `success` / `needs_attention` / `partial` |
| `result` | object | 四部件成稿 + 检查 + 交付 |
| `evidence` | object | 空白支撑、贡献证据、引用映射 |
| `uncertainty` | object | 待核对项、缺元数据、说明 |

## result

| 字段 | 必填 | 内容 |
|---|---|---|
| `introduction_draft` | 是 | 四部件完整成稿全文（可直接编辑） |
| `paragraphs` | 是 | `[{part, text, source_refs[], status}]`；四部件每件至少一段 |
| `source_refs` | 是 | 成稿使用的 work id / claim id / 图表编号 |
| `claims` | 是 | `[{id, text, evidence_refs}]`，每条贡献对应 |
| `checks` | 是 | `draft_review` 的 gate/counts/violations；可选 `pipeline` 摘要 |
| `delivery` | 是 | `{draft_md, draft_review_json, source_map_json}` 路径 |
| `artifacts` | 否 | `draft_review --outdir` 实际写出的 `introduction_draft.md` / `draft_review.json` / `outdir`；路径必须存在 |
| `summary` | 是 | 一行结论：四部件、引用数、空白支撑数、贡献锚点数 |

## evidence

- `principles`：立得住/分得清/说得实/对得上 的具体落实；
- `gap_support`：每条空白 → 支撑 works id 列表；
- `claim_to_evidence`：贡献 id → 图/表/§/数据锚点；
- `unmapped_citations`：无法映射的引用 token（应为空）。

## uncertainty

- `needs_review`：转述忠实度、空白成立性、贡献夸大等待人工回原文核对；
- `missing_metadata`：works 缺作者/年份/来源；
- `note`：脚本只检查结构与映射，不判断学术质量。

## status 判定

- `success`：`draft_review.gate=pass` 或仅剩 warning，四部件齐全、引用全部可映射；
- `needs_attention`：`gate=review`，有 major 待确认但仍交付；
- `partial`：works/材料不足，只能完成部分部件。

## 可编辑产物

- `/app/output/introduction_draft.md`：四部件成稿；
- `/app/output/draft_review.json`：核验结果；
- `/app/output/source_map.json`：引用→works、claim→evidence。

## 最小示例（示意，非正式答案）

```json
{
  "case_id": "example-04",
  "status": "success",
  "result": {
    "introduction_draft": "# 研究背景\n...\n# 相关工作\n...\n# 研究空白\n...\n# 贡献表述\n...",
    "paragraphs": [
      {"part": "研究背景", "text": "...", "source_refs": ["w1", "w2"], "status": "ok"},
      {"part": "相关工作", "text": "...", "source_refs": ["w1", "w2", "w3"], "status": "ok"},
      {"part": "研究空白", "text": "...", "source_refs": ["w1", "w2"], "status": "ok"},
      {"part": "贡献表述", "text": "...", "source_refs": ["c1", "表2"], "status": "ok"}
    ],
    "source_refs": ["w1", "w2", "w3", "c1", "表2"],
    "claims": [{"id": "c1", "text": "提出分组比较框架", "evidence_refs": ["表2"]}],
    "checks": {"draft_review": {"gate": "pass", "counts": {"critical": 0, "major": 0}}},
    "delivery": {"draft_md": "/app/output/introduction_draft.md"},
    "summary": "四部件齐全；3 篇 works 全部引用；2 条空白有支撑；2 条贡献有锚点"
  },
  "evidence": {
    "gap_support": {"少标签场景缺少精度—稳定性权衡": ["w1", "w2"]},
    "claim_to_evidence": {"c1": ["表2"]},
    "unmapped_citations": []
  },
  "uncertainty": {"needs_review": [], "missing_metadata": [], "note": "已按材料核对"}
}
```
