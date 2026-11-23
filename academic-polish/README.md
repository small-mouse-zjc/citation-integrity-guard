# academic-polish-source-preserving

学术语言润色的**保源最小编辑** Skill。面向科研论文、摘要、基金、学位论文、审稿回复等真实文本：先把事实台账与术语表建好，再由 Agent 逐句做语法/术语/语域修改，最后用确定性脚本核对数字、引用、否定、限定强度、术语与段落是否守恒。

## 快速开始

```bash
# 1. 读 case（支持 json/txt/md/docx/pdf）
python scripts/case_io.py /input/case.json --out /app/work/case_texts.json

# 2. 建事实台账
python scripts/polish_audit.py ledger --input /app/work/source.txt \
  --termbase /app/work/termbase.csv --out /app/work/fact_ledger.json

# 3. 写改文（Agent 完成）→ /app/work/polished.md

# 4. 保源核验
python scripts/polish_audit.py check --source /app/work/source.txt \
  --revised /app/work/polished.md --termbase /app/work/termbase.csv \
  --out /app/work/audit.json

# 5. 装配后自检
python scripts/validate_result.py --result /app/output/result.json \
  --outdir /app/output --case /input/case.json
```

## 目录

- `SKILL.md`：五不变量、六阶段、输出契约
- `scripts/case_io.py`：case/文本/docx/pdf 读取
- `scripts/polish_audit.py`：事实台账 + 保源核验
- `scripts/validate_result.py`：结果契约自检
- `scripts/office_io.py`：无依赖 docx 读写
- `references/`：协议、限定梯度、术语规则、编辑分类、输出契约
- `examples/`：正例、反例、自测

## 限制

不生成新论证、不补文献/数据；只做语言层最小编辑。脚本不判断学术质量，只判断守恒与结构。
