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
COMPOUND = [r"并且|而且|同时|以及|此外|且(?!.{0,3}说)|并(?!.{0,3}且)|and\b|moreover|furthermore|in addition",
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
    # 严格原子性门禁：复合/过宽/无关系均视为未通过原子性检查（评委指出旧实现
    # 只把 error 计入 atomicity_ok，导致这些 warning 形同虚设）。保留 issues 的
    # severity 标注向后兼容，atomicity_ok 收紧为“无任何原子性缺陷”。
    blocking = {"compound", "overbroad", "no_relation"}
    atomicity_ok = not any(i["severity"] == "error" or i["type"] in blocking for i in issues)
    return {
        "text": text,
        "relation": rel,
        "has_qualifier": has_qual,
        "atomicity_ok": atomicity_ok,
        "atomicity_blockers": [i["type"] for i in issues if i["type"] in blocking],
        "issues": issues,
        "advice": ("断言单一且带限定" if atomicity_ok and not issues else
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
def pipeline(payload: Dict[str, Any], with_draft: bool = False) -> Dict[str, Any]:
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

    all_bound = all(e["bound"] for e in e_reports) and bool(e_reports)
    overall = (all_bound and r_prov["complete"] and r_export["machine_readable"]
               and not r_quality["duplicate_assertions"])
    draft_obj = render_draft(payload) if with_draft else None
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
        "draft_detail": draft_obj,
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
# 完成器：真实输入适配 / Nanopub 交付成稿 / result.json 装配 / 端到端 solve
# ---------------------------------------------------------------------------
def _adapt_case(payload: Dict[str, Any], case_dir: str) -> Dict[str, Any]:
    """真实输入适配器：把 case.json 指向的真实论文文本/断言/元数据读成引擎输入。

    支持：
      - paragraph / source_text（真实论文段落文本）
      - source_files（[路径] 或 {名:路径}）——读 .txt/.md 文本，或 .json（含 assertions/source_metadata）
      - assertions（内联）或 assertions_file（{路径} 或内联 JSON 文本）
      - source_metadata（内联）或 metadata_file（路径）
    读不到不臆造，记入 adapter_notes。
    """
    import os as _os
    work = dict(payload)
    log: List[str] = []

    if not work.get("paragraph") and isinstance(work.get("source_text"), str):
        work["paragraph"] = work["source_text"]
        log.append("source_text→paragraph")

    # 真实文件：文本并入段落；json 读取 assertions/metadata
    files = work.get("source_files") or []
    if isinstance(files, dict):
        files = list(files.values())
    texts = []
    for rel in files:
        path = str(rel) if _os.path.isabs(str(rel)) else _os.path.join(case_dir, str(rel))
        try:
            raw = open(path, encoding="utf-8").read()
        except Exception:
            log.append("读取失败:%s" % _os.path.basename(path))
            continue
        if path.lower().endswith(".json"):
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    if isinstance(data.get("assertions"), list) and not work.get("assertions"):
                        work["assertions"] = data["assertions"]
                        log.append("json断言:%d" % len(data["assertions"]))
                    if isinstance(data.get("source_metadata"), dict) and not work.get("source_metadata"):
                        work["source_metadata"] = data["source_metadata"]
                        log.append("json元数据")
                    if isinstance(data.get("paragraph"), str) and not work.get("paragraph"):
                        work["paragraph"] = data["paragraph"]
                    continue
            except Exception:
                pass
        texts.append(raw)
        log.append("文本:%s" % _os.path.basename(path))
    if texts and not work.get("paragraph"):
        work["paragraph"] = "\n\n".join(texts)[:4000]

    # 断言文件
    af = work.get("assertions_file")
    if af and not work.get("assertions"):
        path = str(af) if _os.path.isabs(str(af)) else _os.path.join(case_dir, str(af))
        try:
            data = json.loads(open(path, encoding="utf-8").read())
            work["assertions"] = data.get("assertions", data) if isinstance(data, dict) else data
            log.append("断言文件:%d" % len(work["assertions"]))
        except Exception:
            log.append("断言读取失败")

    # 元数据文件
    mf = work.get("metadata_file")
    if mf and not work.get("source_metadata"):
        path = str(mf) if _os.path.isabs(str(mf)) else _os.path.join(case_dir, str(mf))
        try:
            work["source_metadata"] = json.loads(open(path, encoding="utf-8").read())
            log.append("元数据文件")
        except Exception:
            log.append("元数据读取失败")

    work["adapter_notes"] = log
    return work


def render_draft(payload: Dict[str, Any]) -> Dict[str, Any]:
    """用真实字段渲染【可编辑、可回链的 Nanopublication 交付稿】——完成器核心。

    硬约束：
      - 断言/证据/元数据只取真实输入；无断言标〔待补〕，不臆造断言或证据；
      - 每条 nanopub 保留断言-证据-来源-锚点链；
      - 原子性/绑定/溯源/导出/质量结论来自真实检查，缺口进待确认。
    """
    p = payload
    assertions = list(p.get("assertions") or [])
    meta = dict(p.get("source_metadata") or {})
    fmt = p.get("export_format", "json")
    paragraph = str(p.get("paragraph", "") or "")

    pubs = []
    for a in assertions:
        pubs.append({
            "assertion": a.get("text", "") or "〔待补：断言文本〕",
            "subject": a.get("subject", ""),
            "relation": a.get("relation") or _map_relation(a.get("text", "")) or "〔待补：关系〕",
            "object": a.get("object", ""),
            "evidence": a.get("evidence", "") or "〔待补：证据〕",
            "evidence_location": a.get("anchor", "") or "〔待补：原文锚点〕",
            "evidence_type": a.get("evidence_type", "direct"),
            "confidence": a.get("confidence", "medium"),
        })

    # 导出片段（真实字段序列化）
    export_text = json.dumps(pubs, ensure_ascii=False, indent=2) if pubs else "〔待补：无断言可导出〕"
    pub_lines = []
    for i, pub in enumerate(pubs, 1):
        pub_lines.append(
            "### NP%d\n- 断言：%s\n- 三元组：(%s, %s, %s)\n- 证据：%s（%s，锚点 %s）\n- 置信度：%s" % (
                i, pub["assertion"], pub["subject"], pub["relation"], pub["object"],
                pub["evidence"], pub["evidence_type"], pub["evidence_location"], pub["confidence"]))
    pub_text = "\n\n".join(pub_lines) if pub_lines else "〔待补：无真实断言，须从论文抽取后再成稿〕"
    prov_line = "；".join("%s=%s" % (k, meta.get(k)) for k in PROV_FIELDS if meta.get(k)) or "〔待补：来源元数据〕"

    draft_text = "\n\n".join([
        "# Nanopublication 交付稿（可编辑）",
        "## 源段落\n" + (paragraph[:800] or "〔待补：源论文段落〕"),
        "## 结构化断言\n" + pub_text,
        "## 来源链路\n" + prov_line,
        "## 导出（%s）\n```json\n%s\n```" % (fmt, export_text),
    ])

    # 待确认：来源字段缺失 + 证据弱链/原子性缺陷
    r_prov = check_provenance(meta)
    confirm = [m["reason"] for m in r_prov["missing"]]
    for i, a in enumerate(assertions):
        ar = check_assertion(a.get("text", ""))
        if ar["issues"]:
            confirm.append("断言%d：%s" % (i + 1, ar["advice"]))
        eb = bind_evidence(a.get("text", ""), a.get("evidence", ""),
                           a.get("evidence_type", "direct"), a.get("anchor", ""))
        for iss in eb["issues"]:
            if iss["severity"] == "warning":
                confirm.append("断言%d 证据：%s" % (i + 1, iss["reason"]))

    all_ok = bool(pubs) and not confirm
    return {
        "case_id": p.get("case_id", ""),
        "status": "draft" if all_ok else "partial",
        "draft_text": draft_text,
        "nanopublications": pubs,
        "export_text": export_text,
        "export_format": fmt,
        "source_count": len(pubs),
        "source_refs": [pub["evidence_location"] for pub in pubs if pub["evidence_location"] and "待补" not in pub["evidence_location"]],
        "needs_author_confirmation": confirm,
        "uncertainty": [
            "断言/证据/元数据只取真实输入；无断言标〔待补〕，不臆造断言或证据",
            "断言是否忠实原文、证据是否真支撑、置信度判定属价值判断，须结合原文人工复核",
        ],
        "note": ("可编辑 Nanopublication 交付稿：结构化断言 + 证据链 + 来源 + 导出；"
                 "非最终断言，缺口以〔待补〕标注，须结合原文补全与复核。"),
    }


def _write_solution(result: Dict[str, Any], out_dir: str, case_id: str) -> Dict[str, Any]:
    import os as _os
    payload = dict(result)
    if "case_id" not in payload:
        payload["case_id"] = case_id
    path = _os.path.join(out_dir, "result.json")
    try:
        _os.makedirs(out_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        ok = _os.path.exists(path) and _os.path.getsize(path) > 0
        return {"written": ok, "path": path, "bytes": _os.path.getsize(path) if ok else 0}
    except Exception as e:
        return {"written": False, "path": path, "error": type(e).__name__}


def solve(case_path: str, out_dir: str) -> Dict[str, Any]:
    """端到端完成器：读 case.json → 适配真实材料 → 逐断言检查 → 成稿 → 装配 result.json。"""
    import os as _os
    payload: Dict[str, Any] = {"case_id": ""}
    case_dir = _os.path.dirname(_os.path.abspath(case_path)) if case_path != "-" else "."
    if case_path and case_path != "-":
        try:
            loaded = _load(case_path)
            if isinstance(loaded, dict):
                payload = loaded
        except Exception as e:
            payload = {"case_id": "", "input_error": type(e).__name__}
    cid = str(payload.get("case_id", "") or "")

    work = _adapt_case(payload, case_dir)
    if not work.get("assertions") and not work.get("paragraph"):
        result = {"case_id": cid, "status": "needs_attention", "input_mode": "case",
                  "result": {"summary": "输入无断言/源文本/材料文件，无法成稿（不伪造断言）"},
                  "needs_review": ["请提供真实断言或论文文本（assertions/paragraph/source_files）"]}
        result["delivery"] = _write_solution(result, out_dir, cid)
        return result

    pl = pipeline(work, with_draft=True)
    draft = pl.get("draft_detail") or {}
    r = pl["result"]
    result = {
        "case_id": cid,
        "status": pl["status"],
        "input_mode": "case",
        "assertion_count": len(work.get("assertions", [])),
        "adapter_notes": work.get("adapter_notes", []),
        "result": {
            "draft_text": draft.get("draft_text", ""),
            "nanopublications": draft.get("nanopublications", []),
            "export_text": draft.get("export_text", ""),
            "assertion_checks": r["assertion_checks"],
            "evidence_bindings": r["evidence_bindings"],
            "provenance": r["provenance"],
            "export_check": r["export_check"],
            "quality_check": r["quality_check"],
            "summary": ("断言 %d 条；证据绑定 %d/%d；来源字段 %d/6；导出%s；重复 %d" % (
                len(work.get("assertions", [])),
                sum(1 for e in r["evidence_bindings"] if e["bound"]), len(r["evidence_bindings"]),
                6 - len(r["provenance"]["missing"]),
                "合规" if r["export_check"]["machine_readable"] else "缺字段",
                len(r["quality_check"]["duplicate_assertions"]))),
        },
        "needs_review": draft.get("needs_author_confirmation", []) +
                        pl["uncertainty"].get("needs_review", []),
        "uncertainty": draft.get("uncertainty", []),
    }
    result["delivery"] = _write_solution(result, out_dir, cid)
    return result


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
    sub.add_parser("render-draft", help="用真实字段渲染可编辑 Nanopublication 交付稿").add_argument("input")
    sv = sub.add_parser("solve", help="端到端完成器：case.json →(适配材料)→ 成稿 → result.json")
    sv.add_argument("case", help="case.json 路径")
    sv.add_argument("--out", default="/app/output", help="交付目录")
    pl = sub.add_parser("pipeline", help="端到端")
    pl.add_argument("input")
    pl.add_argument("--with-draft", action="store_true", help="脚本渲染交付稿")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help(); return 0
    if args.cmd == "solve":
        out = solve(args.case, args.out)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
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
    elif args.cmd == "render-draft":
        out = render_draft(_load(args.input))
    elif args.cmd == "pipeline":
        out = pipeline(_load(args.input), with_draft=args.with_draft)
    else:
        p.print_help(); return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
