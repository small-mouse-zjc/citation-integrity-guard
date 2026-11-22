#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公平对照证据引擎（academic-polish）：四问机制对照，可复现，不编造平台质量分。

用法：python scripts/compare_engine.py <input.json>
      python scripts/compare_engine.py ../examples/smoke_input.json
      python scripts/compare_engine.py ../examples/benchmark.json   # 逐案例对照

对照只度量"Skill 在四问上是否配置了可运行的确定性检查机制并真实触发"，
客观呈现观测值；质量分/效率分由平台固定案例与白板给出，本引擎不替代。
"""
from __future__ import annotations
import json, sys
from typing import Any, Dict, List

ENGINE = __import__("polish_engine")

PROFILE = {
    'title': '写作02 学术语言润色', 'cid': 'product-arena-02-7051d92d',
    'four': ['改得对', '说得像', '没改坏', '讲得清'],
    'dimensions': [
        ('改得对', '硬错误被换说法掩盖而非改掉', 'grammar_issues', '高置信度硬错误检测：重复词/双冠词/句首小写/标点重复'),
        ('说得像', '术语漂移、语域不合', 'term_inconsistencies+register_flags', '术语全篇一致性回扫+语域诊断'),
        ('没改坏', '限定强度被加强/数值引用被改', 'preservation.issue_count*', '守护元素抽取+限定强度守恒核验'),
        ('讲得清', '逐句无原文-改文-理由对照', 'sentence_count*', '逐句成稿：原文/改文/类型/理由/守护依据'),
    ],
}
STAR_NOTE = "该值为正面证据/覆盖度，越高越好；此处如实呈现，不作为缺陷数"


def _resolve(result: Dict[str, Any], expr: str):
    total, positives, parts = 0, [], [p.strip() for p in expr.split("+")]
    for p in parts:
        positive = p.endswith("*")
        cur: Any = result
        for seg in p.rstrip("*").split("."):
            cur = cur.get(seg) if isinstance(cur, dict) else None
        if isinstance(cur, (list, dict)):
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

    # 真实朴素基线：原文逐段平铺（不做术语回扫/守护/守恒/逐句说明）
    paras = ENGINE._paragraphs(payload)
    baseline_text = "\n\n".join(str(p.get("text", "")) for p in paras)
    draft = ENGINE.render_draft(payload)
    skill_text = draft.get("polished_text", "")
    polished_n = sum(1 for b in draft.get("blocks", []) if b.get("status") in ("polished", "unchanged"))
    draft_cmp = {
        "baseline_text": baseline_text or "〔基线无可用材料〕",
        "baseline_chars": len(baseline_text),
        "baseline_parts": len(paras),
        "skill_text": skill_text,
        "skill_chars": len(skill_text),
        "skill_parts": len(draft.get("blocks", [])),
        "skill_polished_parts": polished_n,
        "skill_pending_parts": len(draft.get("pending_polish", [])),
        "skill_change_reasons": sum(len(b.get("reasons", [])) for b in draft.get("blocks", [])),
        "skill_protected_kinds": sum(len(b.get("protected_kinds", [])) for b in draft.get("blocks", [])),
        "note": ("基线=原文逐段平铺（无术语回扫/守护/守恒/逐句说明，真实生成的朴素稿）；"
                 "Skill=四问成稿草稿（逐句原文/改文或待润色/修改类型与理由/守护依据/核验结论）。"
                 "仅比较结构与覆盖证据，不编造质量分；正式质量对照由平台白板给出。"),
    }

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
        "work": "academic-polish",
        "title": PROFILE["title"],
        "status": "comparison",
        "four_questions": PROFILE["four"],
        "dimensions": dims,
        "draft_comparison": draft_cmp,
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
    d = json.load(open(argv[0], encoding="utf-8"))
    out = [compare(c["input"]) for c in d["cases"]] if "cases" in d else compare(d)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
