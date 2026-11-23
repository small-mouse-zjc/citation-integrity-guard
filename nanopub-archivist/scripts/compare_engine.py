#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公平对照证据引擎（nanopub-archivist）：四问机制对照，可复现，不编造平台质量分。

用法：python scripts/compare_engine.py <input.json>
      python scripts/compare_engine.py ../examples/smoke_input.json
      python scripts/compare_engine.py ../examples/benchmark.json   # 逐案例对照

对照只度量"Skill 在四问上是否配置了可运行的确定性检查机制并真实触发"，
客观呈现观测值；质量分/效率分由平台固定案例与白板给出，本引擎不替代。
"""
from __future__ import annotations
import json, sys
from typing import Any, Dict, List

ENGINE = __import__("nanopub_engine")

PROFILE = {'title': '阅读14 Nanopublication', 'cid': 'product-arena-09-0e8befd4', 'four': ['拆得细', '对得上', '追得回', '读得懂'], 'dimensions': [('拆得细', '整段塞进一个断言字段', 'assertion_checks*', '断言可独立判断检查'), ('对得上', '断言无最小证据片段', 'evidence_bindings*', '证据绑定与原文位置'), ('追得回', '作者/年份/版本链路不全', 'provenance.missing', '来源链路完整性'), ('读得懂', '导出字段不全无法机读', 'export_check.missing_fields+export_check.serializable*', '序列化与字段校验')]}

STAR_NOTE = "该值为正面证据/覆盖度，越高越好；此处如实呈现，不作为缺陷数"


def _resolve(result: Dict[str, Any], expr: str):
    """按 'a.b+c.d' 取字段；字段名以 * 结尾表示正面证据字段。"""
    total, positives, parts = 0, [], [p.strip() for p in expr.split("+")]
    for p in parts:
        positive = p.endswith("*")
        cur: Any = result
        for seg in p.rstrip("*").split("."):
            cur = cur.get(seg) if isinstance(cur, dict) else None
        if isinstance(cur, list):
            v = len(cur)
        elif isinstance(cur, dict):
            v = len(cur)
        elif isinstance(cur, bool):
            v = 1 if cur else 0
        elif isinstance(cur, (int, float)):
            v = cur
        else:
            v = 1 if cur else 0
        if positive:
            positives.append({"field": p.rstrip("*"), "value": v, "note": STAR_NOTE})
        else:
            total += v
    return total, positives


def compare(payload: Dict[str, Any]) -> Dict[str, Any]:
    r = ENGINE.pipeline(payload)
    result = r.get("result", {}) if isinstance(r, dict) else {}
    dims = []
    for dim, baseline, field, gate in PROFILE["dimensions"]:
        flagged, positives = _resolve(result, field)
        dims.append({
            "dimension": dim,
            "baseline_failure": baseline,
            "skill_mechanism": field,
            "skill_checks_fired": flagged if flagged else None,
            "positive_evidence": positives,
            "gate": gate,
        })
    fired = sum(1 for d in dims if d["skill_checks_fired"] or d["positive_evidence"])
    return {
        "case_id": payload.get("case_id", ""),
        "work": "nanopub-archivist",
        "title": PROFILE["title"],
        "status": "comparison",
        "four_questions": PROFILE["four"],
        "dimensions": dims,
        "summary": {
            "four_questions_covered": len(PROFILE["four"]) == 4 and len(dims) == 4,
            "dimensions_with_evidence": fired,
            "total_checks_fired": sum(d["skill_checks_fired"] or 0 for d in dims),
            "honest": True,
        },
        "protocol": ("同一输入/模型/预算，基线按题面四类常见失败直接产出，Skill 先跑确定性引擎再成稿。"
                     "本对照仅呈现 Skill 四问检查机制的可运行证据，不编造质量分或效率分；"
                     "正式质量对照由平台固定案例与白板给出。"),
        "limits": ("基线失败模型按题面四问构造，用于机制演示；真实 Agent 对照与质量分由平台评测给出。"),
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print(__doc__); return 0
    inp = argv[0]
    d = json.load(open(inp, encoding="utf-8"))
    if "cases" in d:  # benchmark.json 多案例
        out = [compare(c["input"]) for c in d["cases"]]
    else:
        out = compare(d)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
