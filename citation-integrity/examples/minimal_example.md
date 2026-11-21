# 最小调用示例

> 下列输入与输出均为**示例**，用于说明接口和流程，**不是**平台的正式测试案例结果，也不得作为预制答案提交。

## 1. 准备输入

`examples/smoke_input.json`：
```json
{
  "case_id": "demo-001",
  "entries": [
    {"id":"wang2020","authors":["Wang, J.","Li, H."],"title":"CO2 flooding and phase behavior in reservoirs","year":2020,"journal":"Fuel","volume":281,"pages":"118-126","doi":"10.1016/j.fuel.2020.118032","type":"article"},
    {"id":"wang2020_dup","authors":["Wang, J.","Li, H."],"title":"CO2 flooding and phase behavior in reservoirs","year":2020,"journal":"Fuel","volume":281,"doi":"https://doi.org/10.1016/j.fuel.2020.118032","type":"article"},
    {"id":"zhang2019","authors":["Zhang, M.","Chen, Y."],"title":"Biomarker geochemistry of natural gas","year":2019,"journal":"Organic Geochemistry","volume":130,"pages":"1-15","type":"article"}
  ],
  "manuscript": "CO2 injection alters phase behavior [2]. Biomarkers constrain gas origin [3]. Review [1,3]."
}
```

要点：`wang2020` 与 `wang2020_dup` 是同一篇文献（DOI 相同、题名相同），应合并；正文引用出现顺序是 2 → 3 → 1，重排后应为 1 → 2 → 3。

## 2. 运行

```bash
# 一键全流程（含落点定位与论断预筛）
python scripts/citation_engine.py pipeline examples/smoke_input.json > result.json
python scripts/citation_engine.py pipeline examples/smoke_input.json --compact > summary.json  # 省 token

# 分项调用
python scripts/citation_engine.py ingest     examples/bib_sample.bib --format bibtex  # 原文解析
python scripts/citation_engine.py normalize  examples/smoke_input.json
python scripts/citation_engine.py renumber   examples/smoke_input.json   # 含 rewritten_manuscript
python scripts/citation_engine.py format     examples/smoke_input.json --standard apa
python scripts/citation_engine.py verify     examples/smoke_input.json
python scripts/citation_engine.py place      examples/smoke_input.json   # 挂得对
python scripts/citation_engine.py claims     examples/smoke_input.json   # 对得上
python scripts/citation_engine.py compare    examples/compare_input.json # 增益对照

# Python 中直接复用子函数
python -c "import sys; sys.path.insert(0,'scripts'); import citation_engine as ce; print(ce.normalize(entries))"
```

## 3. 示意输出（节选，标注为示例）

`normalize` 识别重复并给出证据：
```json
{
  "status": "partial",
  "stats": {"input_count": 3, "output_count": 2, "merged_count": 1},
  "decisions": [{
    "kept_index": 0, "dropped_index": 1, "rule": "doi_exact",
    "confidence": 0.99, "evidence": "DOI 均为 10.1016/j.fuel.2020.118032"
  }]
}
```

`renumber` 的编号映射（旧编号 2 的文献变成新编号 1）：
```json
{"mapping": {"wang2020": 1, "zhang2019": 2}}
```

`result.bibliography`（示例输出，非正式案例结果）：
```
[1] Wang, J, Li, H. CO2 flooding and phase behavior in reservoirs[J]. Fuel, 2020, 281: 118-126. DOI: 10.1016/j.fuel.2020.118032.
[2] Zhang, M, Chen, Y. Biomarker geochemistry of natural gas[J]. Organic Geochemistry, 2019, 130: 1-15.
```

`place` 定位缺引论断句（示意）：
```json
{"stats": {"citation_gaps": 1}, "advice": "发现 1 个论断句缺来源支撑；建议把段末集中引用拆分到各论断句后…"}
```

`claims` 预筛可疑项（示意，仅把 `suspicious_claims` 交模型复核）：
```json
{"stats": {"metadata_anomaly_count": 1, "suspicious_claim_count": 0}, "note": "确定性预筛只给线索，不判编造…"}
```

`compare` 修复前后对照（示意）：
```json
{"summary": {"improved_metrics": 2, "verdict": "增益可验证：修复后问题项减少"}}
```

## 4. 装配正式输出

真实任务中，把平台给定案例解析为 `entries` + `manuscript` 后运行 `pipeline`，再按 `references/output_contract.md` 补充 `claim_source_map`、`uncertainty`、`changes`，写入 `/app/output/result.json`。完整输入/输出样例见 `examples/smoke_input.json` 与 `examples/smoke_output.json`（均已标注为示例）。
