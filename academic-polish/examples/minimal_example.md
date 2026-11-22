# 最小调用示例

> 下列输入与输出均为**示例**，用于说明接口和流程，**不是**平台正式测试案例结果，不得作为预制答案提交。

## 1. 准备输入

`examples/smoke_input.json`（示例片段）：
```json
{
  "case_id": "polish-demo",
  "target_register": "journal",
  "source_lang": "en",
  "paragraphs": [
    {"id":"P1","section":"Abstract","kind":"body",
     "text":"The porosity is approximately 18.5% [1] and the permeability reaches 120 mD (Fig. 2). We propose a novel method that the the significantly improves recovery."}
  ],
  "glossary": [
    {"source":"porosity","target":"孔隙度"},
    {"source":"permeability","target":"渗透率"}
  ],
  "polished": {"P1":"The porosity is approximately 18.5% [1] and the permeability reaches 120 mD (Fig. 2). We propose a method that significantly improves recovery."}
}
```

字段含义：
- `paragraphs`：真实稿件段落（`id`/`section`/`kind`/`text`）。
- `target_register`：目标语域 `journal`/`thesis`/`grant`/`rebuttal`/`abstract`。
- `glossary`：术语表（`source`/`target`），驱动全篇一致性回扫。
- `polished`：真实润色文本（可选，`{段号: 文本}`）。**不提供则脚本标〔待润色〕，不臆造措辞。**

## 2. 确定性检查（守门器）

```bash
python scripts/polish_engine.py segment         examples/smoke_input.json
python scripts/polish_engine.py protect         examples/smoke_input.json
python scripts/polish_engine.py detect_grammar  examples/smoke_input.json
python scripts/polish_engine.py check_terms     examples/smoke_input.json
python scripts/polish_engine.py check_register  examples/smoke_input.json
python scripts/polish_engine.py check_preserve  examples/smoke_input.json
python scripts/polish_engine.py verify          examples/smoke_input.json
python scripts/polish_engine.py pipeline --compact examples/smoke_input.json
```

## 3. 渲染逐句润色成稿草稿（完成器）

```bash
python scripts/polish_engine.py render-draft examples/smoke_input.json
python scripts/polish_engine.py pipeline --with-draft examples/smoke_input.json
```

输出 `blocks`：每句含 `source`（原文）、`target`（真实改文或〔待润色〕）、`change_types`、
`reasons`、`glossary_basis`、`protected_kinds`、`status`。

## 4. 端到端一次交付（推荐）

```bash
python scripts/polish_engine.py solve examples/smoke_input.json --out /app/output
```

从真实 case 出发，一次运行完成：材料适配 → 四问检查 → 逐句润色成稿 → 装配
`/app/output/result.json`，并返回 `delivery`（`written/path/bytes`）回执。
无真实 `polished` 的句标〔待润色〕，脚本绝不臆造润色措辞。

## 5. 公平对照

```bash
python scripts/compare_engine.py examples/smoke_input.json
python scripts/compare_engine.py examples/benchmark.json
```
