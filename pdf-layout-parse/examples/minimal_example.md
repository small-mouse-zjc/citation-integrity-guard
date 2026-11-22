# 最小调用示例

> 下列输入与输出均为**示例**，用于说明接口和流程，**不是**平台正式测试案例结果，不得作为预制答案提交。

## 1. 准备输入（layout JSON）

`examples/smoke_input.json`（带坐标的两页双栏片段）：
```json
{
  "case_id": "smoke-demo",
  "pages": [
    {"page":1, "width":595, "height":842, "lines":[
      {"x0":72,"y0":30,"x1":520,"y1":42,"text":"Journal of Geology","spans":[{"text":"Journal of Geology","size":9,"flags":0,"font":"Times"}]},
      {"x0":72,"y0":60,"x1":520,"y1":82,"text":"Facies Classification with Deep Learning","spans":[{"text":"Facies Classification with Deep Learning","size":16,"flags":16,"font":"Times-Bold"}]},
      {"x0":72,"y0":100,"x1":280,"y1":114,"text":"Abstract","spans":[{"text":"Abstract","size":12,"flags":16,"font":"Times-Bold"}]},
      {"x0":315,"y0":100,"x1":520,"y1":114,"text":"1 Introduction","spans":[{"text":"1 Introduction","size":12,"flags":16,"font":"Times-Bold"}]}
    ]}
  ]
}
```

## 2. 运行

```bash
# 推荐一步到位：真实 case/PDF → 解析 → 装配 /app/output/result.json
python scripts/pdf_layout_engine.py solve /input/case.json --out /app/output

# 或从真实 PDF 导出 layout（多后端自动回退：PyMuPDF→pdfplumber→pdfminer）
python scripts/pdf_layout_engine.py extract paper.pdf --case-id C1 > layout.json

# 一键全流程
python scripts/pdf_layout_engine.py pipeline examples/smoke_input.json > result.json
python scripts/pdf_layout_engine.py pipeline examples/smoke_input.json --compact > summary.json  # 省 token

# 分项
python scripts/pdf_layout_engine.py clean    examples/smoke_input.json
python scripts/pdf_layout_engine.py order    examples/smoke_input.json
python scripts/pdf_layout_engine.py sections examples/smoke_input.json
python scripts/pdf_layout_engine.py tables   examples/smoke_input.json
python scripts/pdf_layout_engine.py formulas examples/smoke_input.json
python scripts/pdf_layout_engine.py captions examples/smoke_input.json
python scripts/pdf_layout_engine.py evidence examples/smoke_input.json
python scripts/pdf_layout_engine.py verify   examples/smoke_input.json

# Python 直接复用
python -c "import sys; sys.path.insert(0,'scripts'); import pdf_layout_engine as p; print(p.pipeline(__import__('json').load(open('examples/smoke_input.json',encoding='utf-8')), compact=True)['result']['summary'])"
```

## 3. 示意输出（节选，标注为示例）

`result.result.reading_text`（按双栏逐栏整段顺序）：
```
Facies Classification with Deep Learning
Abstract
1 Introduction
```

`result.result.summary`（示意）：
```
页数 1；正文行 4；双栏页 1；章节 2；表格 0；公式候选 0；题注 0图/0表；字符覆盖率 100%；证据块 6
```

`result.result.evidence_index[0]`（示意，可回原文）：
```json
{"id":"B001","page":1,"bbox":[72.0,60.0,520.0,82.0],"block_type":"text","text_head":"Facies Classification","source_line":1}
```

## 4. 装配正式输出

真实任务直接用 `solve /input/case.json --out /app/output`：它自动定位平台给定 PDF、`extract` 多后端提取、跑全流程、按 `references/output_contract.md` 装配 `/app/output/result.json`（保留 `case_id`，并在 `delivery` 字段记录落盘回执）。无文字层/找不到 PDF 时如实返回 `needs_review`，不伪造内容。分步用法见上；完整样例见 `examples/smoke_input.json` 与 `examples/smoke_output.json`（均已标注为示例）。预算紧张用 `pipeline --compact`。
