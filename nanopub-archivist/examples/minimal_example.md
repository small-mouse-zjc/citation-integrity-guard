# 最小调用示例（minimal_example）

本文件给出 nanopub-archivist 的最小可运行调用。示例输出均为**示意**，非任何官方评测案例结果。

## 1. 确认引擎可运行

```bash
python scripts/nanopub_engine.py --help
```

## 2. 单步调用：拆得细

```bash
python scripts/nanopub_engine.py check-assertion '{"text":"CNN方法在碳酸盐岩薄片达到0.92准确率。"}'
```

示意输出：
```json
{"text": "CNN方法在碳酸盐岩薄片达到0.92准确率。", "relation": "improves",
 "has_qualifier": true, "atomicity_ok": true, "issues": [],
 "advice": "断言单一且带限定"}
```

## 3. 单步调用：对得上

```bash
python scripts/nanopub_engine.py bind-evidence '{"assertion":"CNN方法在碳酸盐岩薄片达到0.92准确率","evidence":"实验显示CNN准确率0.92","evidence_type":"direct","anchor":"§4"}'
```

示意输出：
```json
{"bound": true, "has_anchor": true, "word_overlap": 1, "issues": [],
 "advice": "证据已绑定且可回链"}
```

## 4. 端到端：pipeline

准备 `input.json`：
```json
{
  "case_id": "demo",
  "paragraph": "在碳酸盐岩薄片中，CNN方法达到0.92准确率[3]。",
  "assertions": [
    {"text": "CNN方法在碳酸盐岩薄片达到0.92准确率", "subject": "CNN方法",
     "relation": "improves", "object": "0.92准确率", "evidence": "实验显示CNN准确率0.92",
     "evidence_type": "direct", "anchor": "§4", "confidence": "high"}
  ],
  "source_metadata": {"paper": "Deep facies", "authors": ["Smith, A."], "year": 2023,
     "version": "v1", "source": "Fuel", "identifier": "doi:10.1016/j.fuel.2023.01"},
  "export_format": "json"
}
```

运行：
```bash
python scripts/nanopub_engine.py pipeline input.json > result.json
```

`result.json` 含：`case_id`、`status`（本例 ok）、`result`（六项检查 + nanopublications）、`evidence`、`uncertainty`。完整字段见 `references/output_contract.md`。

## 5. 自验收

```bash
python examples/selftest.py
# 23/23 通过
```

## 说明

- 断言由 Agent 读真实原文拆分，脚本只做结构/规则校验；
- 价值判断（忠实性、支撑性、置信度）在 `uncertainty.needs_review` 中标出，须人工复核；
- 不臆造断言、证据或来源，材料缺失用 `partial` 并说明限制。
