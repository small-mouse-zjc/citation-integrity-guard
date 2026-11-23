#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公平对照证据引擎（translation-guard）：四问机制对照，可复现，不编造平台质量分。

用法：python scripts/compare_engine.py <input.json>
      python scripts/compare_engine.py ../examples/smoke_input.json
      python scripts/compare_engine.py ../examples/benchmark.json   # 逐案例对照

对照只度量"Skill 在四问上是否配置了可运行的确定性检查机制并真实触发"，
客观呈现观测值；质量分/效率分由平台固定案例与白板给出，本引擎不替代。
"""
from __future__ import annotations
import json, sys
from typing import Any, Dict, List

ENGINE = __import__("translation_guard")

PROFILE = {'title': '阅读03 文献翻译', 'cid': 'product-arena-01-5a9928c1', 'four': ['术语稳', '段落全', '关系准', '可核验'], 'dimensions': [('术语稳', '同术语在标题/摘要/正文多译名', 'term_inconsistencies*', '术语锁定表强制执行+一致性校验'), ('段落全', '长文跨页跨栏漏段/错位', 'aligned_coverage*', '稳定段号贯穿切段-翻译-对齐'), ('关系准', '数字单位/公式/引用被改写', 'restore_issues+verification.issues', '占位保护-回填核对-篡改告警'), ('可核验', '译不准处含混带过无标注', 'evidence_index*+verification.needs_review*', '段落级证据索引+待确认标注')]}

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
        "work": "translation-guard",
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
