# 最小调用示例（示意，非平台正式案例结果）

本示例只用于说明接口与文件形态；正式案例由平台提供，不得把本示例当答案提交。

## 输入

`examples/source.md`（节选）：

```markdown
# Abstract
Recent studies suggest that the method may improve accuracy by 12.5% on the benchmark [1,2].
```

## 步骤

```bash
python scripts/case_io.py /input/case.json --out /app/work/case_texts.json
python scripts/polish_audit.py ledger --input examples/source.md --termbase examples/termbase.csv --out /app/work/ledger.json
# Agent 写出 examples/revised.md
python scripts/polish_audit.py check --source examples/source.md --revised examples/revised.md \
  --termbase examples/termbase.csv --out /app/work/audit.json
```

## 示意输出（audit.json 节选）

```json
{
  "status": "ok",
  "gate": "pass",
  "counts": {"critical": 0, "major": 0, "warning": 0},
  "metrics": {"source_paragraphs": 2, "revised_paragraphs": 2, "numbers_source": 4, "citations_source": 1}
}
```

## 说明

- 示例只改了 `suggest`→`indicate` 等同档措辞；数字、引用、否定、限定全部保留。
- 真实案例必须读 `/input/case.json` 的实际材料，按任务口径润色，并写 `/app/output/result.json`。
