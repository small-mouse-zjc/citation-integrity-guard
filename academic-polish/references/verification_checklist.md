# 核验清单（提交前自查）

- [ ] `python examples/selftest.py` 全绿（D/A/S/TC + 四问）。
- [ ] `python scripts/compare_engine.py examples/smoke_input.json` 可运行，四问覆盖。
- [ ] `python scripts/polish_engine.py solve <case> --out <dir>` 返回 `delivery.written=true`。
- [ ] 无真实润色文时逐句标〔待润色〕，不臆造措辞。
- [ ] 无真实改文时不做守恒核验，显式写 needs_review。
- [ ] 守护元素（数值/引用/图表/公式/化学式/限定/否定）全部抽取且优先级正确。
- [ ] 术语表一致性、语域诊断命中项进 needs_review，不自动改写。
- [ ] result.json 含 case_id / 主结果 / 证据定位 / status / 不确定性 / 修改记录。
- [ ] 资源 ≤50 文本文件、单文件 ≤500KB、总计 ≤2MB、无软链、无凭证残留。
- [ ] trace validate 全部 usable/valid。
