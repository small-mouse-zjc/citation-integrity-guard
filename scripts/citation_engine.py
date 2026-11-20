#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
citation_engine.py — 确定性参考文献一致性引擎
================================================
面向「参考文献与引用管理」挑战的参考实现工具。

设计原则（对应评分维度）：
  - 实际效果/正确性：所有判定基于可回溯的判据，不靠模型臆测。
  - 使用增益：把基础 Agent 容易做错的去重/编号/格式动作固化为确定性算法。
  - 创新增益：可解释去重判据、编号闭包校验、双向一致性检查。
  - 可靠体验：字段缺失、DOI 失败、条目歧义均显式标注，不静默出错。
  - 生态贡献：纯标准库、无网络、可复用、带最小示例。

无任何第三方依赖，Python 3.8+ 可直接运行。

子命令：
  normalize   归一化文献库（去重 + 字段校验 + 证据记录）
  renumber    按正文首次出现顺序重排编号，输出新旧编号映射
  format      将文献库渲染为 GB/T 7714-2015 顺序编码制文后参考文献表
  verify      正文—文末双向一致性核验（悬空引用/未引用条目/编号冲突）
  pipeline    串联 normalize -> renumber -> format -> verify，产出结构化结果

所有输入输出均为 UTF-8 JSON，便于 Agent 直接装配 result.json。
用法见 examples/minimal_example.md。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import OrderedDict, defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple

STATUS_OK = "success"
STATUS_PARTIAL = "partial"
STATUS_UNCERTAIN = "needs_review"


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _strip_latex(s: str) -> str:
    """去掉常见 LaTeX 标记，保留可见文本。"""
    if not s:
        return ""
    s = re.sub(r"\\[a-zA-Z]+\*?\s*\{([^}]*)\}", r"\1", s)  # \emph{x} -> x
    s = re.sub(r"[{}]", "", s)
    s = s.replace("\\&", "&").replace("\\_", "_").replace("\\%", "%")
    s = re.sub(r"\$([^$]*)\$", r"\1", s)
    return s.strip()


def _norm_text(s: str) -> str:
    """归一化文本用于比较：NFKC、小写、去变音、去标点、压空白、去 LaTeX。"""
    if not s:
        return ""
    s = _strip_latex(str(s))
    s = unicodedata.normalize("NFKC", s).lower()
    s = "".join(
        ch for ch in s
        if not unicodedata.combining(ch)
    )
    s = re.sub(r"[^\w\u4e00-\u9fff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_doi(doi: str) -> str:
    """归一化 DOI：去前缀、去大小写、去空白。"""
    if not doi:
        return ""
    d = str(doi).strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = re.sub(r"^doi:\s*", "", d)
    return d.strip().rstrip(".")


def _year_of(entry: Dict[str, Any]) -> Optional[int]:
    y = entry.get("year")
    if y is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(y))
    return int(m.group(0)) if m else None


def _first_author(entry: Dict[str, Any]) -> str:
    authors = entry.get("authors") or []
    if not authors:
        return ""
    return _norm_text(authors[0].split(",")[0])


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# 1) 去重判据（可解释）
# ---------------------------------------------------------------------------
# 判据优先级与置信度。所有命中均记录证据，供人工复核。
DEDUP_RULES = [
    ("doi_exact", 0.99, "DOI 归一化后完全一致（最高可信）"),
    ("title_year_exact", 0.95, "归一化标题完全一致且发表年相同"),
    ("fuzzy_title_author_year", 0.82, "标题相似度≥0.86 且第一作者相同且年份相同"),
    ("version_variant", 0.70, "疑似预印本/正式版或期刊/会议版，需人工确认"),
]


def _dedup_decision(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[bool, float, str, str]:
    """
    返回 (是否判定为同一文献, 置信度, 判据名, 证据说明)。
    保守设计：宁可漏并，不可误并——误并会破坏引用正确性。
    """
    d1, d2 = _norm_doi(a.get("doi", "")), _norm_doi(b.get("doi", ""))
    if d1 and d2 and d1 == d2:
        return True, 0.99, "doi_exact", f"DOI 均为 {d1}"

    t1, t2 = _norm_text(a.get("title", "")), _norm_text(b.get("title", ""))
    y1, y2 = _year_of(a), _year_of(b)
    if t1 and t1 == t2 and y1 and y1 == y2:
        return True, 0.95, "title_year_exact", f"标题『{t1}』+ 年份 {y1}"

    sim = _similarity(t1, t2) if (t1 and t2) else 0.0
    a1, a2 = _first_author(a), _first_author(b)
    if sim >= 0.86 and a1 and a1 == a2 and y1 and y1 == y2:
        return True, 0.82, "fuzzy_title_author_year", (
            f"标题相似度 {sim:.3f} + 第一作者 {a1} + 年份 {y1}"
        )
    if sim >= 0.80 and a1 and a1 == a2:
        return False, 0.70, "version_variant", (
            f"标题相似度 {sim:.3f}、作者一致但年份/版本不同，疑似预印本与正式版，"
            "建议人工确认后再合并"
        )
    return False, 0.0, "no_match", ""


def normalize(entries: List[Dict[str, Any]], threshold: float = 0.82) -> Dict[str, Any]:
    """
    归一化 + 去重。threshold 为接受合并的最低置信度。
    采用「代表条目」策略：组内选字段最完整者为代表，其余记入 merged_from。
    """
    groups: List[Dict[str, Any]] = []
    decisions: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []

    for idx, e in enumerate(entries):
        rec = dict(e)
        rec.setdefault("authors", [])
        rec["_source_index"] = idx
        # 字段完整性提示
        missing = [k for k in ("title", "authors", "year") if not rec.get(k)]
        if missing:
            issues.append({
                "index": idx,
                "type": "missing_fields",
                "fields": missing,
                "message": f"条目 #{idx} 缺少关键字段 {missing}，去重置信度下降",
            })
        placed = False
        for g in groups:
            merged, conf, rule, evidence = _dedup_decision(g["representative"], rec)
            if merged and conf >= threshold:
                g["members"].append(rec)
                # 选字段更完整者作为代表
                if _completeness(rec) > _completeness(g["representative"]):
                    g["representative"] = rec
                decisions.append({
                    "kept_index": g["representative"].get("_source_index"),
                    "dropped_index": idx,
                    "rule": rule,
                    "confidence": conf,
                    "evidence": evidence,
                })
                placed = True
                break
            elif merged and conf < threshold:
                decisions.append({
                    "kept_index": g["representative"].get("_source_index"),
                    "dropped_index": idx,
                    "rule": rule,
                    "confidence": conf,
                    "evidence": evidence,
                    "action": "not_merged_below_threshold",
                })
        if not placed:
            groups.append({"representative": rec, "members": [rec]})

    out_entries = []
    for gi, g in enumerate(groups, 1):
        rep = dict(g["representative"])
        rep["dedup_group"] = gi
        rep["merged_from"] = [
            m.get("_source_index") for m in g["members"] if m is not g["representative"]
        ]
        out_entries.append(rep)

    merged_low = [d for d in decisions if d.get("action") == "not_merged_below_threshold"]
    status = STATUS_UNCERTAIN if merged_low else (STATUS_PARTIAL if issues else STATUS_OK)
    return {
        "status": status,
        "entries": out_entries,
        "decisions": decisions,
        "issues": issues,
        "stats": {
            "input_count": len(entries),
            "output_count": len(out_entries),
            "merged_count": len(entries) - len(out_entries),
            "needs_review_count": len(merged_low),
        },
    }


def _completeness(e: Dict[str, Any]) -> int:
    fields = ("title", "authors", "year", "journal", "volume", "issue",
              "pages", "doi", "type", "abstract")
    return sum(1 for f in fields if e.get(f))


# ---------------------------------------------------------------------------
# 2) 编号重排（正文首次出现顺序）
# ---------------------------------------------------------------------------
CITE_RE = re.compile(r"\[(\d+(?:\s*[,，\-–]\s*\d+)*)\]")


def _expand_citation(token: str) -> List[int]:
    """展开 [1,2,3-5] 形式的编号为列表。"""
    nums: List[int] = []
    for part in re.split(r"[,，]", token):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b:
                nums.extend(range(a, b + 1))
            else:
                nums.append(a)
        elif part.isdigit():
            nums.append(int(part))
    return nums


def renumber(manuscript: str, entries: List[Dict[str, Any]],
             id_field: str = "id") -> Dict[str, Any]:
    """
    按正文首次出现顺序重排编号。
    entries 中每个条目应有稳定标识（默认 'id'）。若用旧编号引用，
    可用 old_index_field='old_number'。这里支持两种引用域：
      - 正文 [n] 指向旧编号 -> 通过 old_number 映射到条目
      - 正文 [@key] 指向条目 id -> 通过 @ 语法
    """
    # 建立 旧编号/键 -> 条目 的索引
    key_to_entry: Dict[str, Dict[str, Any]] = {}
    for i, e in enumerate(entries, 1):
        eid = str(e.get(id_field) or e.get("key") or f"ref{i}")
        e["_eid"] = eid
        key_to_entry[eid.lower()] = e
        if e.get("old_number") is not None:
            key_to_entry[str(e["old_number"])] = e

    # 扫描正文，记录首次出现顺序
    order: List[str] = []
    occurrences: List[Tuple[str, str, List[int]]] = []

    at_re = re.compile(r"\[?@([A-Za-z0-9_\-:]+)\]?")

    def scan_line(line: str, lineno: int):
        # @key 语法
        for m in at_re.finditer(line):
            k = m.group(1).lower()
            if k in key_to_entry:
                eid = key_to_entry[k]["_eid"]
                if eid not in order:
                    order.append(eid)
                occurrences.append({"line": lineno, "token": m.group(0), "eids": [eid]})
        # [n] 语法
        for m in CITE_RE.finditer(line):
            nums = _expand_citation(m.group(1))
            eids = []
            for n in nums:
                e = key_to_entry.get(str(n))
                if e:
                    eid = e["_eid"]
                    if eid not in order:
                        order.append(eid)
                    eids.append(eid)
            occurrences.append({"line": lineno, "token": m.group(0), "eids": eids,
                                "unresolved_numbers": [n for n in nums if str(n) not in key_to_entry]})

    for ln, line in enumerate(manuscript.splitlines(), 1):
        scan_line(line, ln)

    # 未被引用的条目追加到末尾（保证列表完整）
    for e in entries:
        if e["_eid"] not in order:
            order.append(e["_eid"])

    mapping = OrderedDict()
    for new_num, eid in enumerate(order, 1):
        mapping[eid] = new_num

    unresolved = []
    for occ in occurrences:
        for n in occ.get("unresolved_numbers", []):
            unresolved.append({"line": occ["line"], "token": occ["token"], "number": n})

    out_entries = []
    for e in entries:
        ne = dict(e)
        ne["new_number"] = mapping.get(e["_eid"])
        ne.pop("_eid", None)
        out_entries.append(ne)

    status = STATUS_PARTIAL if unresolved else STATUS_OK
    return {
        "status": status,
        "mapping": dict(mapping),
        "entries": out_entries,
        "order": order,
        "occurrences": occurrences,
        "unresolved": unresolved,
        "stats": {
            "total_entries": len(entries),
            "cited_entries": len(order) - sum(1 for e in entries if e.get("_eid") not in order),
            "unresolved_refs": len(unresolved),
        },
    }


# ---------------------------------------------------------------------------
# 3) GB/T 7714-2015 格式化
# ---------------------------------------------------------------------------
TYPE_LABEL = {
    "article": "[J]", "journal": "[J]",
    "book": "[M]", "thesis": "[D]", "phdthesis": "[D]", "mastersthesis": "[D]",
    "conference": "[C]", "inproceedings": "[C]",
    "report": "[R]", "standard": "[S]", "patent": "[P]",
    "online": "[EB/OL]", "electronic": "[EB/OL]",
    "preprint": "[EB/OL]", "misc": "[Z]",
}


def _format_authors_gb(authors: List[str]) -> str:
    """GB/T 7714：列出前 3 位，超过 3 位加『, 等』；避免句末双点。"""
    if not authors:
        return ""
    # 统一去掉每位作者尾部已有的句点，交给渲染层统一补一个
    cleaned = [str(a).strip().rstrip(".") for a in authors]
    if len(cleaned) <= 3:
        return ", ".join(cleaned)
    return ", ".join(cleaned[:3]) + ", 等"


def format_entry_gb(e: Dict[str, Any], number: int) -> str:
    """渲染单条为 GB/T 7714-2015 顺序编码制条目。"""
    authors = _format_authors_gb(e.get("authors") or [])
    title = _strip_latex(str(e.get("title", "")))
    year = e.get("year", "")
    label = TYPE_LABEL.get(str(e.get("type", "")).lower(), "[Z]")
    parts = [f"[{number}]", f"{authors}."] if authors else [f"[{number}]"]
    parts.append(f"{title}{label}.")
    etype = str(e.get("type", "")).lower()
    if etype in ("article", "journal"):
        journal = e.get("journal") or e.get("container_title", "")
        vol = e.get("volume", "")
        issue = e.get("issue", "")
        pages = e.get("pages", "")
        parts.append(f"{journal}, {year}" if journal else str(year))
        if vol:
            parts[-1] += f", {vol}"
        if issue:
            parts[-1] += f"({issue})"
        if pages:
            parts[-1] += f": {pages}"
        parts[-1] += "."
    elif etype in ("book", "thesis", "phdthesis", "mastersthesis", "report", "standard", "patent"):
        publisher = e.get("publisher") or e.get("institution") or e.get("school", "")
        place = e.get("address", "")
        if place and publisher:
            parts.append(f"{place}: {publisher}, {year}.")
        elif publisher:
            parts.append(f"{publisher}, {year}.")
        else:
            parts.append(f"{year}.")
    elif etype in ("conference", "inproceedings"):
        conf = e.get("booktitle") or e.get("container_title", "")
        publisher = e.get("publisher", "")
        seg = f"{conf}, {year}" if conf else str(year)
        if publisher:
            seg += f": {publisher}"
        parts.append(seg + ".")
    else:
        parts.append(f"{year}.")

    doi = _norm_doi(e.get("doi", ""))
    if doi:
        parts.append(f"DOI: {doi}.")
    return " ".join(p for p in parts if p)


def format_bib(entries: List[Dict[str, Any]], number_field: str = "new_number") -> Dict[str, Any]:
    lines = []
    warnings = []
    for e in entries:
        num = e.get(number_field)
        if num is None:
            warnings.append({"title": e.get("title"), "message": "条目缺少编号，跳过格式化"})
            continue
        lines.append(format_entry_gb(e, int(num)))
    ordered = sorted(zip([e.get(number_field) or 0 for e in entries], lines),
                     key=lambda x: x[0])
    return {
        "status": STATUS_PARTIAL if warnings else STATUS_OK,
        "references": [ln for _, ln in ordered],
        "warnings": warnings,
        "standard": "GB/T 7714-2015 (顺序编码制)",
    }


# ---------------------------------------------------------------------------
# 4) 一致性核验（双向）
# ---------------------------------------------------------------------------
def verify(manuscript: str, entries: List[Dict[str, Any]],
           number_field: str = "new_number") -> Dict[str, Any]:
    """
    双向核验：
      正向：正文出现的每个编号都能在文末列表找到（无悬空引用）
      反向：文末每个条目都被正文引用（无多余条目）
      连续性：文末编号从 1 连续递增
    """
    cited: List[int] = []
    for m in CITE_RE.finditer(manuscript):
        cited.extend(_expand_citation(m.group(1)))
    cited_set = set(cited)

    listed = sorted(int(e[number_field]) for e in entries if e.get(number_field) is not None)
    listed_set = set(listed)

    dangling = sorted(cited_set - listed_set)          # 正文有、列表无
    uncited = sorted(listed_set - cited_set)           # 列表有、正文无
    duplicates = sorted({n for n in listed if listed.count(n) > 1})
    expected = set(range(1, len(listed_set) + 1)) if listed_set else set()
    gaps = sorted(expected - listed_set)
    out_of_range = sorted(n for n in listed_set if n < 1 or n > len(entries))

    problems = []
    if dangling:
        problems.append("悬空引用：正文引用了文末不存在的编号 " + str(dangling))
    if uncited:
        problems.append("未被引用：文末条目未在正文出现 " + str(uncited))
    if duplicates:
        problems.append("编号重复：" + str(duplicates))
    if gaps:
        problems.append("编号不连续，缺号：" + str(gaps))
    if out_of_range:
        problems.append("编号越界：" + str(out_of_range))

    return {
        "status": STATUS_OK if not problems else STATUS_PARTIAL,
        "consistent": not problems,
        "cited_numbers": sorted(cited_set),
        "listed_numbers": listed,
        "dangling_citations": dangling,
        "uncited_entries": uncited,
        "duplicate_numbers": duplicates,
        "numbering_gaps": gaps,
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# 5) 全流程
# ---------------------------------------------------------------------------
def pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload = {
      "case_id": str,
      "entries": [ {...}, ... ],
      "manuscript": str,
      "threshold": float (可选)
    }
    """
    entries = payload.get("entries") or []
    manuscript = payload.get("manuscript", "")
    threshold = float(payload.get("threshold", 0.82))

    norm = normalize(entries, threshold=threshold)
    ren = renumber(manuscript, norm["entries"])
    fmt = format_bib(ren["entries"])
    ver = verify(manuscript, ren["entries"])

    statuses = [norm["status"], ren["status"], fmt["status"], ver["status"]]
    overall = STATUS_OK
    if STATUS_UNCERTAIN in statuses:
        overall = STATUS_UNCERTAIN
    elif STATUS_PARTIAL in statuses:
        overall = STATUS_PARTIAL

    return {
        "case_id": payload.get("case_id", ""),
        "status": overall,
        "pipeline": {
            "normalize": norm,
            "renumber": ren,
            "format": fmt,
            "verify": ver,
        },
        "result": {
            "bibliography": fmt["references"],
            "number_mapping": ren["mapping"],
            "consistency": {
                "consistent": ver["consistent"],
                "problems": ver["problems"],
            },
            "evidence": {
                "dedup_decisions": norm["decisions"],
                "dedup_issues": norm["issues"],
                "unresolved_citations": ren["unresolved"],
            },
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load_json_arg(arg: str) -> Any:
    if arg == "-":
        return json.load(sys.stdin)
    with open(arg, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="确定性参考文献一致性引擎")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("normalize")
    sp.add_argument("input", help="JSON 文件，- 表示 stdin；含 entries 或为条目数组")
    sp.add_argument("--threshold", type=float, default=0.82)

    sp = sub.add_parser("renumber")
    sp.add_argument("input", help="JSON：含 manuscript 与 entries")
    sp.add_argument("--id-field", default="id")

    sp = sub.add_parser("format")
    sp.add_argument("input", help="JSON：含 entries")
    sp.add_argument("--number-field", default="new_number")

    sp = sub.add_parser("verify")
    sp.add_argument("input", help="JSON：含 manuscript 与 entries")
    sp.add_argument("--number-field", default="new_number")

    sub.add_parser("pipeline").add_argument("input", help="JSON：case_id/entries/manuscript")

    args = p.parse_args(argv)
    data = _load_json_arg(args.input)

    if args.cmd == "normalize":
        entries = data.get("entries", data) if isinstance(data, dict) else data
        out = normalize(entries, threshold=args.threshold)
    elif args.cmd == "renumber":
        out = renumber(data.get("manuscript", ""), data.get("entries", []),
                       id_field=args.id_field)
    elif args.cmd == "format":
        out = format_bib(data.get("entries", []), number_field=args.number_field)
    elif args.cmd == "verify":
        out = verify(data.get("manuscript", ""), data.get("entries", []),
                     number_field=args.number_field)
    elif args.cmd == "pipeline":
        out = pipeline(data)
    else:
        p.error("未知命令")
        return 2

    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
