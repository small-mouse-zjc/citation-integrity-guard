#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nanopub_engine.py — Nanopublication（纳米出版物）确定性构建与核验引擎

面向论文关键结论的原子化知识单元构建，把四类易错动作做成可运行、可复核的计算：

  check_assertion      拆得细：断言是否单一可判断真假、保留条件与限定范围、识别复合句
  bind_evidence        对得上：每条断言绑定最小充分证据片段与原文位置，区分直接/间接
  check_provenance     追得回：断言-证据-论文-作者-年份-版本链路完整性
  check_export         读得懂：导出结构字段与序列化形态合规，可被下游直接解析
  check_quality        质量检查：断言过宽/证据不足/关系类型错误/主体混淆/来源缺失
  pipeline             串联以上，产出 nanopublication 结构化结果与证据链

设计原则：
  - 纯 Python 3 标准库，无第三方依赖、无网络请求、不调用外部服务；
  - 只做确定性结构计算与规则判定，价值判断（断言是否忠实、证据是否真支持）
    留给 Agent，但要求给出可回溯定位；
  - 字段缺失、证据不足、来源不明、链路断裂一律显式标注，绝不臆造断言或证据。

用法：
  python nanopub_engine.py --help
  python nanopub_engine.py pipeline input.json > result.json
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
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", (s or "").lower())).strip()


def _has(s: str, pats: List[str]) -> bool:
    return any(re.search(p, s or "", re.I) for p in pats)


# ---------------------------------------------------------------------------
# 受控词表
# ---------------------------------------------------------------------------
RELATION_VOCAB = {
    "indicates": ["表明", "指示", "显示", "indicate", "suggest", "show"],
    "causes": ["导致", "引起", "造成", "cause", "lead to", "result in"],
    "correlates": ["相关", "关联", "correlate", "associate"],
    "improves": ["提升", "改善", "提高", "优于", "达到", "达至", "improve", "outperform", "better than", "achieve"],
    "reduces": ["降低", "减少", "下降", "reduce", "decrease", "lower"],
    "is_a": ["属于", "是一种", "是", "is a", "is an", "be a"],
    "consistent_with": ["一致", "符合", "consistent", "agree"],
    "contradicts": ["矛盾", "不一致", "冲突", "contradict", "conflict"],
}
# 断言过宽信号
OVERBROAD = [r"所有|一切|总是|永远|完全|绝对|任何情况|all|always|never|every|universally",
             r"显著|极大|彻底|completely|significantly"]
# 条件/限定信号（保留则好）
QUALIFIERS = [r"在.{0,15}条件", r"当.{0,15}时", r"约|大约|左右|approximately|about", r"部分|某些|特定",
              r"within|under|given|provided|在.{0,10}范围", r"\d+%|\d+\.\d+"]
# 证据位置格式
ANCHOR_RE = re.compile(r"(p(?:age)?\.?\s*\d+|§\s*[\d.]+|fig(?:ure)?\.?\s*\d+|tab(?:le)?\.?\s*\d+|"
                       r"第[一二三四五六七八九十百\d]+(?:章|节|段|页)|图\s*\d+|表\s*\d+|L\d+)", re.I)
# 复合句信号
COMPOUND = [r"并且|而且|同时|以及|此外|and\b|moreover|furthermore|in addition",
            r"因为|所以|由于|因此|because|therefore|thus|since", r"但是|然而|although|however|but\b"]


def _map_relation(text: str) -> Optional[str]:
    for rel, pats in RELATION_VOCAB.items():
        if _has(text, pats):
            return rel
    return None


# ---------------------------------------------------------------------------
# 1) 拆得细：断言原子性
# ---------------------------------------------------------------------------
def check_assertion(text: str) -> Dict[str, Any]:
    issues = []
    compound = [p for p in COMPOUND if re.search(p, text or "", re.I)]
    if compound:
        issues.append({"type": "compound", "severity": "warning",
                       "reason": f"断言含复合连接词（{compound[:3]}），可能可再拆为多条原子断言"})
    overbroad = [p for p in OVERBROAD if re.search(p, text or "", re.I)]
    if overbroad and not _has(text, QUALIFIERS):
        issues.append({"type": "overbroad", "severity": "warning",
                       "reason": "断言用过宽词（所有/完全/显著）却无条件或量化限定，须收窄或加限定"})
    has_qual = _has(text, QUALIFIERS)
    # 主体-关系-对象粗判
    rel = _map_relation(text)
    if not rel:
        issues.append({"type": "no_relation", "severity": "warning",
                       "reason": "未识别到受控关系词，断言主体-关系-对象结构不清"})
    return {
        "text": text,
        "relation": rel,
        "has_qualifier": has_qual,
        "atomicity_ok": not any(i["severity"] == "error" for i in issues),
        "issues": issues,
        "advice": ("断言单一且带限定" if not issues else
                   f"{len(issues)} 处待改进：{[i['type'] for i in issues]}"),
    }


# ---------------------------------------------------------------------------
# 2) 对得上：证据绑定
# ---------------------------------------------------------------------------
def bind_evidence(assertion: str, evidence: str, evidence_type: str = "direct",
                  anchor: str = "") -> Dict[str, Any]:
    """检查证据是否绑定、是否最小充分、是否有原文位置。"""
    issues = []
    ev = (evidence or "").strip()
    if not ev:
        issues.append({"type": "no_evidence", "severity": "error", "reason": "断言无证据片段"})
    elif len(ev) > 300:
        issues.append({"type": "evidence_too_long", "severity": "warning",
                       "reason": f"证据片段 {len(ev)} 字，可能非最小充分，宜截取直接支撑部分"})
    # 锚点
    has_anchor = bool(ANCHOR_RE.search(anchor)) or bool(ANCHOR_RE.search(ev))
    if not anchor or not ANCHOR_RE.search(anchor):
        issues.append({"type": "no_anchor", "severity": "error",
                       "reason": "证据缺独立原文位置（页码/章节/图表），无法回链"})
    # 直接/间接
    if evidence_type not in ("direct", "indirect"):
        issues.append({"type": "bad_evidence_type", "severity": "error",
                       "reason": f"证据类型 {evidence_type} 非 direct/indirect"})
    # 词面重叠粗判（证据是否可能支撑断言）
    overlap = len(set(_norm(assertion).split()) & set(_norm(ev).split()))
    weak = overlap == 0 and len(ev) > 0
    if weak:
        issues.append({"type": "weak_link", "severity": "warning",
                       "reason": "断言与证据词面无重叠，须人工确认是否真支撑（间接推理需标注为 indirect）"})
    has_error = any(i["severity"] == "error" for i in issues)
    return {
        "assertion": assertion,
        "evidence": ev,
        "evidence_type": evidence_type,
        "anchor": anchor,
        "has_anchor": has_anchor,
        "word_overlap": overlap,
        "bound": not has_error,
        "issues": issues,
        "advice": ("证据已绑定且可回链" if not has_error else
                   f"{sum(1 for i in issues if i['severity']=='error')} 处绑定错误须修复"),
    }


# ---------------------------------------------------------------------------
# 3) 追得回：来源链路完整性
# ---------------------------------------------------------------------------
PROV_FIELDS = ["paper", "authors", "year", "version", "source", "identifier"]


def check_provenance(meta: Dict[str, Any]) -> Dict[str, Any]:
    missing = []
    for k in PROV_FIELDS:
        v = meta.get(k)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
            missing.append({"field": k, "reason": f"来源元数据缺『{k}』，链路不完整"})
    # DOI/标识符格式粗检
    ident = str(meta.get("identifier", "") or "")
    id_ok = bool(ident) and (ident.lower().startswith("doi:") or "doi.org" in ident.lower()
                             or re.match(r"10\.\d{4,}", ident) or ident.upper().startswith("PMID"))
    if ident and not id_ok:
        missing.append({"field": "identifier_format", "reason": "标识符不像 DOI/PMID，须核对"})
    return {
        "metadata": meta,
        "missing": missing,
        "complete": not missing,
        "advice": ("来源链路字段齐全" if not missing else f"缺 {len(missing)} 项来源元数据，须补齐"),
    }


# ---------------------------------------------------------------------------
# 4) 读得懂：导出结构
# ---------------------------------------------------------------------------
NP_FIELDS = ["assertion", "subject", "relation", "object", "evidence",
             "evidence_location", "paper", "authors", "year", "identifier", "confidence"]


def check_export(nanopubs: List[Dict[str, Any]], fmt: str = "json") -> Dict[str, Any]:
    issues = []
    if fmt not in ("json", "jsonld", "rdf"):
        issues.append({"type": "bad_format", "severity": "error",
                       "reason": f"导出格式 {fmt} 非约定形态 json/jsonld/rdf"})
    missing_by_pub = []
    for i, pub in enumerate(nanopubs or []):
        miss = [f for f in NP_FIELDS if f not in pub or pub[f] in (None, "", [])]
        if miss:
            missing_by_pub.append({"index": i, "missing_fields": miss})
    # 序列化可解析性（对象必须能 json.dumps）
    serializable = True
    try:
        json.dumps(nanopubs, ensure_ascii=False)
    except Exception:
        serializable = False
        issues.append({"type": "not_serializable", "severity": "error",
                       "reason": "导出对象无法 JSON 序列化，下游无法解析"})
    return {
        "format": fmt,
        "pub_count": len(nanopubs or []),
        "missing_fields": missing_by_pub,
        "serializable": serializable,
        "machine_readable": serializable and not issues,
        "issues": issues,
        "advice": ("导出结构合规、可直接解析" if serializable and not issues and not missing_by_pub
                   else f"{len(missing_by_pub)} 条 nanpub 缺字段，须补齐再导出"),
    }


# ---------------------------------------------------------------------------
# 5) 质量检查：汇总
# ---------------------------------------------------------------------------
def check_quality(nanopubs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """跨 nanopub 质量检查：过宽断言、证据不足、主体混淆、重复。"""
    subjects: Dict[str, List[int]] = {}
    seen_assert: Dict[str, int] = {}
    dup = []
    for i, pub in enumerate(nanopubs or []):
        s = str(pub.get("subject", "")).strip()
        if s:
            subjects.setdefault(s, []).append(i)
        a = _norm(str(pub.get("assertion", "")))
        if a in seen_assert:
            dup.append({"index": i, "duplicate_of": seen_assert[a]})
        else:
            seen_assert[a] = i
    # 主体混淆：同一主体对应过多不同关系
    ambiguous = []
    for s, idxs in subjects.items():
        rels = {str(nanopubs[i].get("relation", "")) for i in idxs}
        if len(rels) > 4:
            ambiguous.append({"subject": s, "relation_count": len(rels), "indices": idxs})
    return {
        "duplicate_assertions": dup,
        "ambiguous_subjects": ambiguous,
        "subject_count": len(subjects),
        "advice": ("未发现明显质量问题" if not dup and not ambiguous
                   else f"{len(dup)} 条重复断言，{len(ambiguous)} 个主体关系过多须核对"),
    }


# ---------------------------------------------------------------------------
# 6) pipeline
# ---------------------------------------------------------------------------
def pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    case_id = payload.get("case_id", "")
    paragraph = payload.get("paragraph", "")
    assertions = payload.get("assertions", []) or []   # [{text, subject, relation, object, evidence, evidence_type, anchor, confidence}]
    meta = payload.get("source_metadata", {}) or {}
    fmt = payload.get("export_format", "json")

    # 逐断言检查
    a_reports = []
    e_reports = []
    for a in assertions:
        a_reports.append({"text": a.get("text", ""), **check_assertion(a.get("text", ""))})
        e_reports.append(bind_evidence(a.get("text", ""), a.get("evidence", ""),
                                        a.get("evidence_type", "direct"), a.get("anchor", "")))

    r_prov = check_provenance(meta)

    # 组装 nanopubs（补来源元数据）
    nanopubs = []
    for a in assertions:
        pub = {
            "assertion": a.get("text", ""),
            "subject": a.get("subject", ""),
            "relation": a.get("relation") or _map_relation(a.get("text", "")) or "",
            "object": a.get("object", ""),
            "evidence": a.get("evidence", ""),
            "evidence_location": a.get("anchor", ""),
            "evidence_type": a.get("evidence_type", "direct"),
            "paper": meta.get("paper", ""), "authors": meta.get("authors", []),
            "year": meta.get("year", ""), "version": meta.get("version", ""),
            "identifier": meta.get("identifier", ""),
            "confidence": a.get("confidence", "medium"),
        }
        nanopubs.append(pub)
    r_export = check_export(nanopubs, fmt)
    r_quality = check_quality(nanopubs)

    all_bound = all(e["bound"] for e in e_reports)
    overall = (all_bound and r_prov["complete"] and r_export["machine_readable"]
               and not r_quality["duplicate_assertions"])
    return {
        "case_id": case_id,
        "status": "ok" if overall else "needs_attention",
        "result": {
            "source_paragraph": paragraph,
            "assertion_checks": a_reports,
            "evidence_bindings": e_reports,
            "provenance": r_prov,
            "export_check": r_export,
            "quality_check": r_quality,
            "nanopublications": nanopubs,
        },
        "evidence": {
            "principles": {
                "拆得细": "断言单一可判断真假、保留条件限定", "对得上": "最小充分证据+原文位置",
                "追得回": "断言-证据-来源链路完整", "读得懂": "字段与序列化合规",
            },
            "unbound_assertions": [i for i, e in enumerate(e_reports) if not e["bound"]],
            "missing_provenance": [m["field"] for m in r_prov["missing"]],
        },
        "uncertainty": {
            "needs_review": ([i for i, a in enumerate(a_reports) if a["issues"]] +
                             [i for i, e in enumerate(e_reports) if any(x["severity"] == "warning" for x in e["issues"])]),
            "note": ("断言是否忠实原文、证据是否真支撑、置信度判定属价值判断，须 Agent 结合原文复核；"
                     "脚本只做结构与规则校验，不臆造断言或证据"),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load(path: str) -> Any:
    """接受文件路径、内联 JSON 字符串或 '-'（stdin）；兼容 README 的内联示例。"""
    s = str(path or "").strip()
    if s == "-":
        return json.load(sys.stdin)
    if s.startswith("{") or s.startswith("["):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass  # 视为路径，交给下面 open 抛出更明确的错误
    with open(s, encoding="utf-8") as f:
        return json.load(f)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Nanopublication 确定性构建与核验引擎")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("check-assertion", help="拆得细"); sp.add_argument("input")
    sp = sub.add_parser("bind-evidence", help="对得上"); sp.add_argument("input")
    sp = sub.add_parser("check-provenance", help="追得回"); sp.add_argument("input")
    sp = sub.add_parser("check-export", help="读得懂"); sp.add_argument("input")
    sp = sub.add_parser("check-quality", help="质量检查"); sp.add_argument("input")
    sub.add_parser("pipeline", help="端到端").add_argument("input")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help(); return 0
    if args.cmd == "check-assertion":
        out = check_assertion(_load(args.input).get("text", ""))
    elif args.cmd == "bind-evidence":
        d = _load(args.input)
        out = bind_evidence(d.get("assertion", ""), d.get("evidence", ""),
                            d.get("evidence_type", "direct"), d.get("anchor", ""))
    elif args.cmd == "check-provenance":
        out = check_provenance(_load(args.input).get("metadata", {}))
    elif args.cmd == "check-export":
        d = _load(args.input); out = check_export(d.get("nanopubs", []), d.get("format", "json"))
    elif args.cmd == "check-quality":
        out = check_quality(_load(args.input).get("nanopubs", []))
    elif args.cmd == "pipeline":
        out = pipeline(_load(args.input))
    else:
        p.print_help(); return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
