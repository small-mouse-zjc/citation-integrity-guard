# 输入输出字段契约（Output Contract）

## 输入：layout JSON

```json
{
  "case_id": "案例标识",
  "pages": [
    {
      "page": 1,
      "width": 595.0,
      "height": 842.0,
      "lines": [
        {
          "x0": 72.0, "y0": 100.0, "x1": 520.0, "y1": 114.0,
          "text": "Abstract",
          "spans": [
            {"text": "Abstract", "size": 12.0, "flags": 16, "font": "Times-Bold"}
          ]
        }
      ]
    }
  ]
}
```

- 坐标原点左上、y 向下、单位 pt；与 PDF 原生坐标系一致。
- `text` 是回退字段；`spans[].text` 拼接是逐字保真的首选来源。
- `size` 字号用于上下标/标题判定；`flags` 位 16 常表示粗体（PyMuPDF 约定）；`font` 字体名。
- 字段缺失如实留空，不臆造坐标。

## 输出：pipeline result.json

```json
{
  "case_id": "案例标识",
  "status": "success | partial | needs_review",
  "pipeline": { "...各步骤完整结果...（--compact 时省略）": {} },
  "result": {
    "reading_text": "按版面顺序的可编辑正文",
    "structure": [{"title":"1 Introduction","level":1,"page":1,"children":[]}],
    "sections": [{"text":"1 Introduction","kind":"numbered","level":1,"page":1,"order":3}],
    "tables": [{"page":1,"rows":3,"cols":3,"markdown":"| ... |"}],
    "formulas": [{"text":"L = - Σ p log q (1)","rendered":"...","number":"1",
                  "has_greek":true,"page":1}],
    "captions": [{"kind":"figure","number":1,"text":"Figure 1. ...","page":1}],
    "evidence_index": [{"id":"B001","page":1,"bbox":[72,100,520,114],
                        "block_type":"text","text_head":"Abstract","source_line":3}],
    "verification": {"status":"success","consistent":true,"coverage":0.98,
                     "body_chars":1200,"out_chars":1176,"problems":[]},
    "summary": "页数 2；正文行 29；双栏页 2；章节 7；表格 1；公式 1；题注 1图/1表；覆盖率 100%；证据块 41"
  }
}
```

字段说明：

- `reading_text`：按 `order` 的 `ordered` 序列拼接，跨页换行；不改写措辞。
- `structure` / `sections`：章节层级树与扁平列表，`level` 由编号深度或 `kind` 决定。
- `tables[].markdown`：Markdown 表格；`continuations` 给跨页续表候选（在 `pipeline.tables`）。
- `formulas[].rendered`：保真符号文本（保留真实 Unicode 希腊字母，不把 ASCII 改为希腊字母）。
- `evidence_index`：每个块含 `page` + `bbox` + `block_type` + `text_head`；被剔除的页眉页脚为 `excluded:*` 类型。
- `verification.coverage`：`out_chars / body_chars`，正文字符覆盖率；<90% 进 `problems`。
- `status`：整体状态。任一 `needs_review` → needs_review；否则任一 `partial` → partial；否则 success。

## 装配正式 result.json

真实任务按 `references/output_contract.md` 保留 `case_id` 与所有字段；平台还会要求 `output_contract` 中的"证据与边界/运行状态"字段——把 `evidence_index`、`verification.problems`、`unreadable`、`needs_review` 填入对应项。可编辑产物（reading_text、表格 Markdown）另存 `/app/output/` 下文件。预算紧张时用 `pipeline --compact`，只输出 `status/summary/bibliography` 类摘要与核验结论。
