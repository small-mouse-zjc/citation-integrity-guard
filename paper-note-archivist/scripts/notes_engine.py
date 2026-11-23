#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notes_engine.py — 文献总结与结构化笔记的确定性引擎

面向真实论文的阅读笔记环节，把四类高频易错动作从 LLM 自由发挥
变成可运行、可复核、可回溯的确定性计算：

  check_section_alignment  对得上：笔记骨架是否跟随论文自身章节与论证顺序
  check_card_fields        留得住：研究问题/数据/方法条件/发现/局限/前提 字段是否齐全
  verify_anchors           找得回：每条关键笔记的锚点能否指回原文具体位置
  normalize_knowledge      用得上：知识点去重、术语/缩写归一、可检索性
  build_reading_card       生成统一字段的论文卡片（可并排比较）
  pipeline                 串联以上，产出结构化结果与证据链

设计原则：
  - 纯 Python 3 标准库，无第三方依赖、无网络请求；
  - 只做确定性结构计算与规则判定，价值判断（笔记是否忠实原文、锚点是否真对应）
    留给 Agent，但要求给出可回溯定位；
  - 未报告、字段缺失、锚点悬空、术语冲突一律显式标注，绝不臆造内容或锚点。

用法：
  python notes_engine.py --help
  python notes_engine.py pipeline input.json > result.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    s = (s or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", s)).strip()


def _has(s: str, patterns: List[str]) -> bool:
    return any(re.search(p, s or "", re.I) for p in patterns)


# ---------------------------------------------------------------------------
# 1) 对得上：章节对齐
# ---------------------------------------------------------------------------
SECTION_HINTS = {
    "abstract": [r"摘要", r"abstract"],
    "intro": [r"引言", r"绪论", r"introduction", r"背景", r"background"],
    "related": [r"相关工作", r"related work", r"文献综述", r"literature"],
    "method": [r"方法", r"实验设置", r"method", r"approach", r"实验设计"],
    "result": [r"结果", r"实验", r"result", r"experiment", r"发现"],
    "discussion": [r"讨论", r"discussion", r"分析"],
    "conclusion": [r"结论", r"展望", r"conclusion", r"总结"],
}
SECTION_ORDER = ["abstract", "intro", "related", "method", "result", "discussion", "conclusion"]


def check_section_alignment(paper_sections: List[str], note_sections: List[str]) -> Dict[str, Any]:
    """检查笔记骨架是否与论文自身章节顺序一致。

    paper_sections / note_sections: 章节标题或含标题的文本列表（按出现顺序）。
    """
    def classify(items: List[str]) -> List[str]:
        seq = []
        for it in items or []:
            found = None
            for key, pats in SECTION_HINTS.items():
                if _has(str(it), pats):
                    found = key; break
            if found and (not seq or seq[-1] != found):
                seq.append(found)
        return seq

    p_seq = classify(paper_sections)
    n_seq = classify(note_sections)
    paper_keys = set(p_seq)
    note_keys = set(n_seq)
    missing = sorted(paper_keys - note_keys)
    extra = sorted(note_keys - paper_keys)

    # 顺序一致性：笔记章节相对顺序是否与论文一致（用公共子序列的顺序判断）
    common_p = [k for k in p_seq if k in note_keys]
    common_n = [k for k in n_seq if k in paper_keys]
    order_ok = common_p == common_n
    inversions = []
    if not order_ok:
        pos = {k: i for i, k in enumerate(common_p)}
        for i in range(len(common_n)):
            for j in range(i + 1, len(common_n)):
                if pos.get(common_n[i], 0) > pos.get(common_n[j], 0):
                    inversions.append((common_n[i], common_n[j]))

    return {
        "paper_sequence": p_seq,
        "note_sequence": n_seq,
        "missing_sections": missing,
        "extra_sections": extra,
        "order_consistent": order_ok,
        "inversions": inversions,
        "aligned": order_ok and not missing,
        "advice": ("笔记骨架与论文章节对齐" if order_ok and not missing
                   else f"笔记漏章节 {missing} 或顺序不一致（倒序 {inversions[:3]}），须按论文自身结构重排"),
    }


# ---------------------------------------------------------------------------
# 2) 留得住：论文卡片字段完整性
# ---------------------------------------------------------------------------
CARD_FIELDS = {
    "question": {"label": "研究问题", "patterns": [r"研究问题", r"问题", r"aim", r"objective", r"research question"]},
    "data": {"label": "数据", "patterns": [r"数据", r"样本", r"dataset", r"data", r"语料"]},
    "method_conditions": {"label": "方法条件", "patterns": [r"方法", r"条件", r"设置", r"method", r"setup", r"前提"]},
    "findings": {"label": "主要发现", "patterns": [r"发现", r"结果", r"finding", r"result", r"结论"]},
    "limitations": {"label": "局限", "patterns": [r"局限", r"限制", r"不足", r"limitation", r"future"]},
    "premises": {"label": "结论前提", "patterns": [r"前提", r"假设", r"适用条件", r"仅在", r"当.{0,10}时", r"premise", r"assumption", r"under"]},
}


def check_card_fields(card: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    required = required or list(CARD_FIELDS.keys())
    report = {}
    missing = []
    for key in required:
        meta = CARD_FIELDS.get(key, {"label": key, "patterns": [key]})
        val = card.get(key, "")
        present = bool(str(val).strip())
        # 若字段空，尝试在 note 全文里找（兼容只有 note 字段的卡片）
        if not present and card.get("note"):
            present = _has(str(card.get("note")), meta["patterns"])
        report[key] = {"label": meta["label"], "present": present}
        if not present:
            missing.append({"field": key, "label": meta["label"],
                            "hint": f"卡片缺『{meta['label']}』，尤其注意让结论成立的前提条件"})
    n = sum(1 for v in report.values() if v["present"])
    return {
        "fields": report,
        "present_count": n,
        "required_count": len(required),
        "missing": missing,
        "complete": not missing,
        "advice": ("卡片字段齐全" if not missing
                   else f"缺 {len(missing)} 个字段：{[m['label'] for m in missing]}，须补记或标注未报告"),
    }


# ---------------------------------------------------------------------------
# 3) 找得回：锚点回链校验
# ---------------------------------------------------------------------------
ANCHOR_RE = re.compile(r"(p(?:age)?\.?\s*\d+|§\s*[\d.]+|fig(?:ure)?\.?\s*\d+|tab(?:le)?\.?\s*\d+|"
                       r"第[一二三四五六七八九十百\d]+(?:章|节|段|页)|图\s*\d+|表\s*\d+)", re.I)


def verify_anchors(notes: List[Dict[str, Any]], valid_anchors: Optional[List[str]] = None) -> Dict[str, Any]:
    """校验每条关键笔记是否带可回链的原文锚点。

    notes: [{id, text, anchor}]；valid_anchors 若提供，则锚点须在其中（模拟原文定位表）。
    """
    valid_set = {_norm(a) for a in (valid_anchors or [])} if valid_anchors else None
    results = []
    no_anchor, bad_anchor = [], []
    for nt in notes or []:
        anchor = str(nt.get("anchor", "") or "").strip()
        text = str(nt.get("text", "") or "")
        has_pattern = bool(ANCHOR_RE.search(anchor)) or bool(ANCHOR_RE.search(text))
        valid = bool(anchor) and (valid_set is None or _norm(anchor) in valid_set)
        item = {"id": nt.get("id"), "anchor": anchor, "has_anchor_format": has_pattern,
                "valid": valid and has_pattern}
        results.append(item)
        if not anchor or not has_pattern:
            no_anchor.append({"id": nt.get("id"), "text": text[:60],
                              "reason": "笔记缺具体锚点（页码/章节/图表），只能给笼统出处"})
        elif valid_set is not None and not valid:
            bad_anchor.append({"id": nt.get("id"), "anchor": anchor,
                               "reason": "锚点不在原文可用定位表中，可能指错位置"})
    anchored = sum(1 for r in results if r["valid"])
    return {
        "notes": results,
        "note_count": len(results),
        "anchored_count": anchored,
        "no_anchor": no_anchor,
        "bad_anchor": bad_anchor,
        "all_anchored": not no_anchor and not bad_anchor,
        "advice": ("每条笔记均可回链原文" if not no_anchor and not bad_anchor
                   else f"{len(no_anchor)} 条缺锚点、{len(bad_anchor)} 条锚点无效，须补具体定位"),
    }


# ---------------------------------------------------------------------------
# 4) 用得上：知识点去重与归一
# ---------------------------------------------------------------------------
def _sim(a: str, b: str) -> float:
    sa, sb = set(_norm(a).split()), set(_norm(b).split())
    if not sa or not sb:
        return 0.0
    # 中文按 2-gram 补充
    def grams(s):
        s = _norm(s).replace(" ", "")
        return set(s[i:i+2] for i in range(len(s)-1)) or {s}
    inter = len(sa & sb) + len(grams(a) & grams(b))
    union = len(sa | sb) + len(grams(a) | grams(b))
    return inter / union if union else 0.0


SYNONYM_HINT = r"(CNN|卷积神经网络|convolutional neural network)|(SVM|支持向量机)|(准确率|accuracy)|(薄片|thin section)"


def normalize_knowledge(points: List[Dict[str, Any]], dup_threshold: float = 0.72) -> Dict[str, Any]:
    """知识点去重与术语/缩写归一，产出可检索条目。"""
    canon: List[Dict[str, Any]] = []
    merges = []
    for p in points or []:
        label = str(p.get("label") or p.get("term") or p.get("text", "")).strip()
        best_i, best_s = None, 0.0
        for i, c in enumerate(canon):
            s = _sim(label, c["label"])
            if s > best_s:
                best_i, best_s = i, s
        if best_i is not None and best_s >= dup_threshold:
            merges.append({"duplicate": label, "merged_into": canon[best_i]["label"],
                           "similarity": round(best_s, 3)})
            # 合并别名/锚点
            if p.get("anchor"):
                canon[best_i].setdefault("aliases_anchors", []).append(p["anchor"])
            continue
        entry = {"label": label, "definition": p.get("definition", ""),
                 "anchor": p.get("anchor", ""), "type": p.get("type", "concept")}
        # 缩写/同义提示
        if re.search(SYNONYM_HINT, label, re.I):
            entry["synonym_hint"] = True
        canon.append(entry)
    return {
        "entries": canon,
        "entry_count": len(canon),
        "merged_count": len(merges),
        "merges": merges,
        "needs_review": [m for m in merges if m["similarity"] < 0.85],
        "advice": (f"归一后 {len(canon)} 条，合并 {len(merges)} 条重复"
                   + ("；低相似合并须人工确认" if any(m["similarity"] < 0.85 for m in merges) else "")),
    }


# ---------------------------------------------------------------------------
# 5) 论文卡片
# ---------------------------------------------------------------------------
def build_reading_card(fields: Dict[str, Any]) -> Dict[str, Any]:
    """生成统一字段的论文卡片，缺失字段标注未报告，不臆造。"""
    card = {}
    missing = []
    for key, meta in CARD_FIELDS.items():
        val = fields.get(key)
        if val is None or (isinstance(val, str) and not val.strip()) or (isinstance(val, list) and not val):
            card[key] = {"value": "", "status": "not_reported", "label": meta["label"]}
            missing.append(meta["label"])
        else:
            card[key] = {"value": val, "status": "reported", "label": meta["label"],
                         "anchor": fields.get(f"{key}_anchor", "")}
    return {
        "card": card,
        "missing_fields": missing,
        "comparable": not missing,
        "advice": ("卡片字段齐全，可与同领域论文并排比较" if not missing
                   else f"{len(missing)} 个字段未报告，已标注 not_reported，不得臆造"),
    }


# ---------------------------------------------------------------------------
# 6) pipeline
# ---------------------------------------------------------------------------
def pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    case_id = payload.get("case_id", "")
    paper_sections = payload.get("paper_sections", []) or []
    note_sections = payload.get("note_sections", []) or []
    card = payload.get("card", {}) or {}
    notes = payload.get("notes", []) or []
    valid_anchors = payload.get("valid_anchors")
    points = payload.get("knowledge_points", []) or []

    r_align = check_section_alignment(paper_sections, note_sections)
    r_card = check_card_fields(card, payload.get("required_fields"))
    r_anchor = verify_anchors(notes, valid_anchors)
    r_know = normalize_knowledge(points, payload.get("dup_threshold", 0.72))
    r_readcard = build_reading_card(card)

    overall = (r_align["aligned"] and r_card["complete"] and
               r_anchor["all_anchored"] and not r_know["needs_review"])
    notes_text = "\n".join(str(n.get("text") or n.get("summary") or n.get("note") or "")
                           for n in notes if isinstance(n, dict))
    notes_present = len(notes_text.strip()) >= 200 and len(notes) >= 1
    status = "ok" if (overall and notes_present) else ("partial" if not notes_present else "needs_attention")
    return {
        "case_id": case_id,
        "status": status,
        "result": {
            "section_alignment": r_align,
            "card_fields": r_card,
            "anchor_verification": r_anchor,
            "knowledge_normalization": r_know,
            "reading_card": r_readcard,
            "structured_notes": notes,
            "notes_metrics": {"count": len(notes), "chars": len(notes_text),
                              "present": notes_present, "required_min_chars": 200},
        },
        "evidence": {
            "principles": {
                "对得上": "笔记骨架跟随论文章节", "留得住": "关键字段与前提齐备",
                "找得回": "每条笔记可回链原文", "用得上": "知识点去重归一、可检索",
            },
            "missing_anchors": [n["id"] for n in r_anchor["no_anchor"]],
            "bad_anchors": [n["id"] for n in r_anchor["bad_anchor"]],
            "knowledge_merges": r_know["merges"],
        },
        "uncertainty": {
            "missing_fields": r_card["missing"] + r_readcard["missing_fields"],
            "needs_review": r_know["needs_review"],
            "note": ("笔记是否忠实原文、锚点是否真对应属价值判断，须 Agent 结合原文复核；"
                     "脚本只做结构与格式校验，不臆造未报告内容"),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="文献结构化笔记确定性引擎")
    sub = p.add_subparsers(dest="cmd")

    for name, helptext in [
        ("check-section-alignment", "对得上：章节对齐"),
        ("check-card-fields", "留得住：卡片字段完整性"),
        ("verify-anchors", "找得回：锚点回链校验"),
        ("normalize-knowledge", "用得上：知识点去重归一"),
        ("build-reading-card", "生成统一论文卡片"),
    ]:
        sp = sub.add_parser(name, help=helptext); sp.add_argument("input", help="JSON 输入")

    sub.add_parser("pipeline", help="端到端").add_argument("input", help="JSON 全量输入")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help(); return 0

    if args.cmd == "check-section-alignment":
        d = _load(args.input); out = check_section_alignment(d.get("paper_sections", []), d.get("note_sections", []))
    elif args.cmd == "check-card-fields":
        d = _load(args.input); out = check_card_fields(d.get("card", {}), d.get("required"))
    elif args.cmd == "verify-anchors":
        d = _load(args.input); out = verify_anchors(d.get("notes", []), d.get("valid_anchors"))
    elif args.cmd == "normalize-knowledge":
        d = _load(args.input); out = normalize_knowledge(d.get("points", []), d.get("dup_threshold", 0.72))
    elif args.cmd == "build-reading-card":
        d = _load(args.input); out = build_reading_card(d.get("fields", {}))
    elif args.cmd == "pipeline":
        out = pipeline(_load(args.input))
    else:
        p.print_help(); return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
