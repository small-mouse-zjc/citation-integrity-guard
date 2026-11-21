#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
citation_engine.py — 确定性参考文献一致性引擎
================================================
面向「参考文献与引用管理」挑战的参考实现工具。

设计原则（对应评分维度）：
  - 实际效果/正确性：所有判定基于可回溯的判据，不靠模型臆测。
  - 使用增益：把基础 Agent 容易做错的去重/编号/格式/论断预筛动作固化为确定性算法。
  - 创新增益：可解释去重判据、编号闭包校验、双向一致性、论断级引用匹配预筛、
               引用落点定位、修复前后可验证对照。
  - 可靠体验：字段缺失、DOI 失败、条目歧义均显式标注，不静默出错。
  - 生态贡献：纯标准库、无网络、可复用、带测试题集与失败模式案例。

无任何第三方依赖，Python 3.8+ 可直接运行。

子命令：
  normalize   归一化文献库（去重 + 字段校验 + 证据记录）
  ingest      解析 BibTeX / RIS / CNKI / 键值文本原文为结构化 entries（省手工转换）
  renumber    按正文首次出现顺序重排编号，输出新旧映射 + 改写后的可编辑正文
  format      渲染文后参考文献表（内置 GB/T 7714—2015；附 APA 展示规范可扩展）
  verify      正文—文末双向一致性 + 首次出现顺序校验
  place       引用落点定位：识别需要来源支撑的论断句与建议插入位置（挂得对）
  claims      论断核验预筛：元数据异常/编造线索/主题错配，把逐句复核降为可疑项（对得上）
  compare     修复前后对照：问题数与差异逐项可验证（增益可验证）
  pipeline    全流程串联，产出结构化结果 + 紧凑摘要（compact）

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

CURRENT_YEAR = 2026


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


STOPWORDS = set(
    "的 了 和 与 及 在 是 为 对 中 该 这 其 并 等 也 而 从 以 于 上 下 "
    "the a an of and or in on for to with by is are was were this that we "
    "our their its as at from using based new study paper results result"
    .split()
)


def _content_words(text: str, min_len: int = 2) -> List[str]:
    """抽取内容词：英文单词 + 中文二字块，去停用词，供确定性主题预筛。"""
    s = _norm_text(text)
    words: List[str] = []
    for tok in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", s):
        if tok in STOPWORDS or len(tok) < min_len:
            continue
        if re.match(r"^[a-z0-9]+$", tok):
            words.append(tok)
        else:
            # 中文按相邻二字块切，保留一定词汇覆盖
            words.extend(tok[i:i + 2] for i in range(len(tok) - 1))
    return words


def render_citation(nums: List[int]) -> str:
    """把编号列表渲染为紧凑引用标记 [2,4-6]。"""
    nums = sorted({int(n) for n in nums})
    if not nums:
        return ""
    parts: List[str] = []
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        if j - i >= 2:
            parts.append(f"{nums[i]}-{nums[j]}")
        elif j - i == 1:
            parts.extend([str(nums[i]), str(nums[j])])
        else:
            parts.append(str(nums[i]))
        i = j + 1
    return "[" + ",".join(parts) + "]"


# ---------------------------------------------------------------------------
# 1) 去重判据（可解释）
# ---------------------------------------------------------------------------
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
    """归一化 + 去重。threshold 为接受合并的最低置信度。"""
    groups: List[Dict[str, Any]] = []
    decisions: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []

    for idx, e in enumerate(entries):
        rec = dict(e)
        rec.setdefault("authors", [])
        rec["_source_index"] = idx
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
            elif conf > 0:
                # 有判据命中但未达合并阈值：包括低置信模糊匹配与 version_variant
                # （后者返回 merged=False）。一律记入待复核，避免疑似重复被静默丢弃。
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
# 2) 编号重排（正文首次出现顺序）+ 可编辑正文改写
# ---------------------------------------------------------------------------
CITE_RE = re.compile(r"\[(\d+(?:\s*[,，\-–]\s*\d+)*)\]")
AT_RE = re.compile(r"\[?@([A-Za-z0-9_\-:]+)\]?")


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
             id_field: str = "id", rewrite: bool = True) -> Dict[str, Any]:
    """
    按正文首次出现顺序重排编号。
    支持 [n] / [1,2,3-5]（旧编号）与 [@key] 两种引用域。
    rewrite=True 时额外产出按新编号改写的可编辑正文（不改动措辞，仅替换引用标记）。
    """
    manuscript = manuscript or ""  # 畸形输入：None/缺字段归一为空串，避免崩溃
    key_to_entry: Dict[str, Dict[str, Any]] = {}
    for i, e in enumerate(entries, 1):
        eid = str(e.get(id_field) or e.get("key") or f"ref{i}")
        e["_eid"] = eid
        key_to_entry[eid.lower()] = e
        if e.get("old_number") is not None:
            key_to_entry[str(e["old_number"])] = e

    order: List[str] = []
    occurrences: List[Dict[str, Any]] = []

    def scan_line(line: str, lineno: int):
        hits: List[Tuple[int, int, str, List[str], List[int], str]] = []
        for m in AT_RE.finditer(line):
            k = m.group(1).lower()
            if k in key_to_entry:
                e = key_to_entry[k]
                eid = e["_eid"]
                if eid not in order:
                    order.append(eid)
                hits.append((m.start(), m.end(), m.group(0), [eid], [], "at"))
        for m in CITE_RE.finditer(line):
            nums = _expand_citation(m.group(1))
            eids: List[str] = []
            unresolved = []
            for n in nums:
                e = key_to_entry.get(str(n))
                if e:
                    eid = e["_eid"]
                    if eid not in order:
                        order.append(eid)
                    eids.append(eid)
                else:
                    unresolved.append(n)
            # 避免同一位置被 @ 与 [n] 双重记录
            span = (m.start(), m.end())
            if not any(s == span[0] and en == span[1] for s, en, *_ in hits):
                occurrences.append({"line": lineno, "token": m.group(0),
                                    "eids": eids, "kind": "num",
                                    "unresolved_numbers": unresolved,
                                    "start": m.start(), "end": m.end()})
        for s, en, tok, eids, unresolved, kind in hits:
            occurrences.append({"line": lineno, "token": tok, "eids": eids,
                                "kind": kind, "unresolved_numbers": unresolved,
                                "start": s, "end": en})

    for ln, line in enumerate(manuscript.splitlines(), 1):
        scan_line(line, ln)

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

    # 为每个出现点计算新编号与改写标记
    by_line: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for occ in occurrences:
        new_nums = [mapping[eid] for eid in occ["eids"] if eid in mapping]
        occ["new_numbers"] = new_nums
        occ["rewritten_token"] = render_citation(new_nums + occ.get("unresolved_numbers", []))
        by_line[occ["line"]].append(occ)

    rewritten_lines: List[str] = []
    if rewrite:
        for ln, line in enumerate(manuscript.splitlines(), 1):
            edits = sorted(
                [(o["start"], o["end"], o["rewritten_token"]) for o in by_line.get(ln, [])],
                key=lambda x: -x[0],
            )
            new_line = line
            for s, en, rep in edits:
                new_line = new_line[:s] + rep + new_line[en:]
            rewritten_lines.append(new_line)

    status = STATUS_PARTIAL if unresolved else STATUS_OK
    result = {
        "status": status,
        "mapping": dict(mapping),
        "entries": out_entries,
        "order": order,
        "occurrences": [
            {k: v for k, v in o.items() if k not in ("start", "end")}
            for o in occurrences
        ],
        "unresolved": unresolved,
        "stats": {
            "total_entries": len(entries),
            "cited_entries": sum(1 for eid in order if eid in mapping),
            "unresolved_refs": len(unresolved),
        },
    }
    if rewrite:
        result["rewritten_manuscript"] = "\n".join(rewritten_lines)
        result["rewrite_changes"] = [
            {"line": o["line"], "from": o["token"], "to": o["rewritten_token"]}
            for o in occurrences if o["token"] != o["rewritten_token"]
        ]
    return result


# ---------------------------------------------------------------------------
# 3) 文后参考文献表格式化（GB/T 7714 主 + APA 展示规范可扩展）
# ---------------------------------------------------------------------------
TYPE_LABEL = {
    "article": "[J]", "journal": "[J]",
    "book": "[M]", "thesis": "[D]", "phdthesis": "[D]", "mastersthesis": "[D]",
    "conference": "[C]", "inproceedings": "[C]",
    "report": "[R]", "standard": "[S]", "patent": "[P]",
    "online": "[EB/OL]", "electronic": "[EB/OL]",
    "preprint": "[EB/OL]", "misc": "[Z]",
}


def _has_chinese(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def _format_authors_gb(authors: List[str]) -> str:
    """GB/T 7714：前 3 位；中文第 4 位起『, 等』，英文『, et al.』。"""
    if not authors:
        return ""
    cleaned = [str(a).strip().rstrip(".") for a in authors]
    if len(cleaned) <= 3:
        return ", ".join(cleaned)
    all_chinese = all(_has_chinese(a) for a in cleaned)
    tail = ", 等" if all_chinese else ", et al."
    return ", ".join(cleaned[:3]) + tail


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


def _format_authors_apa(authors: List[str]) -> str:
    """
    APA 7th：姓, 名首字母.；两人用 &；三人以上列前六再省略号。
    作为『规范可扩展』的展示实现，不替代正式排版核对。
    """
    if not authors:
        return ""
    def one(a: str) -> str:
        a = str(a).strip().rstrip(".")
        if "," in a:
            last, given = a.split(",", 1)
            initials = " ".join(w[0].upper() + "." for w in given.strip().split())
            return f"{last.strip()}, {initials}".strip().rstrip(",")
        toks = a.split()
        if len(toks) == 1:
            return toks[0]
        last = toks[-1]
        initials = " ".join(w[0].upper() + "." for w in toks[:-1])
        return f"{last}, {initials}"
    rendered = [one(a) for a in authors]
    if len(rendered) == 1:
        return rendered[0]
    if len(rendered) == 2:
        return f"{rendered[0]}, & {rendered[1]}"
    if len(rendered) <= 6:
        return ", ".join(rendered[:-1]) + f", & {rendered[-1]}"
    return ", ".join(rendered[:6]) + ", ... " + rendered[-1]


def format_entry_apa(e: Dict[str, Any]) -> str:
    """渲染单条为 APA 7th 风格（用于证明规范可扩展；正式使用需人工核对版本细则）。"""
    authors = _format_authors_apa(e.get("authors") or [])
    year = e.get("year", "")
    title = _strip_latex(str(e.get("title", "")))
    seg = f"{authors} ({year}). {title}."
    etype = str(e.get("type", "")).lower()
    if etype in ("article", "journal"):
        journal = e.get("journal") or e.get("container_title", "")
        vol = e.get("volume", "")
        issue = e.get("issue", "")
        pages = e.get("pages", "")
        tail = journal
        if vol:
            tail += f", {vol}"
        if issue:
            tail += f"({issue})"
        if pages:
            tail += f", {pages}"
        seg += f" {tail}."
    doi = _norm_doi(e.get("doi", ""))
    if doi:
        seg += f" https://doi.org/{doi}"
    return re.sub(r"\s+", " ", seg).strip()


def format_bib(entries: List[Dict[str, Any]], number_field: str = "new_number",
               standard: str = "gb7714") -> Dict[str, Any]:
    warnings: List[Dict[str, Any]] = []
    lines: List[str] = []
    for e in entries:
        num = e.get(number_field)
        if num is None:
            warnings.append({"title": e.get("title"), "message": "条目缺少编号，跳过格式化"})
            continue
        if standard == "apa":
            lines.append((int(num), format_entry_apa(e)))
        else:
            lines.append((int(num), format_entry_gb(e, int(num))))
    lines.sort(key=lambda x: x[0])
    return {
        "status": STATUS_PARTIAL if warnings else STATUS_OK,
        "references": [ln for _, ln in lines],
        "warnings": warnings,
        "standard": "APA 7th (展示实现，需人工核对版本细则)" if standard == "apa"
                    else "GB/T 7714-2015 (顺序编码制)",
    }


# ---------------------------------------------------------------------------
# 4) 一致性核验（双向 + 首次出现顺序）
# ---------------------------------------------------------------------------
def verify(manuscript: str, entries: List[Dict[str, Any]],
           number_field: str = "new_number") -> Dict[str, Any]:
    """
    双向核验：
      正向：正文引用的编号都能在文末找到（无悬空）
      反向：文末条目都被正文引用（无多余）
      连续性：编号从 1 连续递增、无重复、无越界
    附加：首次出现顺序（顺序编码制应按首次出现递增）。
    为保持既有语义，顺序问题单列字段，不改变 consistent（除非传入 check_order=True）。
    """
    manuscript = manuscript or ""  # 畸形输入归一化
    cited: List[int] = []
    for m in CITE_RE.finditer(manuscript):
        cited.extend(_expand_citation(m.group(1)))
    cited_set = set(cited)

    listed = sorted(int(e[number_field]) for e in entries if e.get(number_field) is not None)
    listed_set = set(listed)

    dangling = sorted(cited_set - listed_set)
    uncited = sorted(listed_set - cited_set)
    duplicates = sorted({n for n in listed if listed.count(n) > 1})
    expected = set(range(1, len(listed_set) + 1)) if listed_set else set()
    gaps = sorted(expected - listed_set)
    out_of_range = sorted(n for n in listed_set if n < 1 or n > len(entries))

    first_seen: List[int] = []
    for n in cited:
        if n not in first_seen:
            first_seen.append(n)
    order_violations: List[Dict[str, Any]] = []
    if first_seen and first_seen != sorted(first_seen):
        order_violations.append({
            "type": "first_appearance_order",
            "actual": first_seen,
            "expected": sorted(first_seen),
            "note": "顺序编码制要求编号按正文首次出现递增；建议 renumber 重排",
        })

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
        "first_appearance_order": first_seen,
        "order_violations": order_violations,
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# 5) ingest：文献库原文解析（BibTeX / RIS / CNKI / 键值文本）
# ---------------------------------------------------------------------------
BIB_FIELD_MAP = {
    "title": "title", "author": "authors", "journal": "journal",
    "journaltitle": "journal", "booktitle": "booktitle", "year": "year",
    "date": "year", "volume": "volume", "number": "issue", "issue": "issue",
    "pages": "pages", "doi": "doi", "publisher": "publisher", "address": "address",
    "school": "school", "institution": "institution", "abstract": "abstract",
    "url": "url", "keywords": "keywords",
}
BIB_TYPE_MAP = {
    "article": "article", "book": "book", "phdthesis": "thesis",
    "mastersthesis": "thesis", "inproceedings": "conference",
    "conference": "conference", "techreport": "report", "report": "report",
    "manual": "misc", "misc": "misc",
}


def _split_bib_fields(body: str) -> List[str]:
    fields: List[str] = []
    depth = 0
    buf = ""
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            fields.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        fields.append(buf)
    return fields


def _clean_bib_value(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] in '{"' and v[-1] in '}"':
        v = v[1:-1]
    return _strip_latex(v).strip()


def parse_bibtex(text: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    # 括号配平扫描：支持单行/多行 BibTeX，字段值可含 {...}（不依赖 \n} 结尾）
    s = text or ""
    parsed: List[Tuple[str, str, str]] = []  # (type, key, body)
    i = 0
    while True:
        at = s.find("@", i)
        if at < 0:
            break
        m = re.match(r"@(\w+)\s*\{", s[at:])
        if not m:
            i = at + 1
            continue
        btype = m.group(1)
        ob = at + m.end() - 1
        depth, j = 1, ob + 1
        while j < len(s) and depth > 0:
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
            j += 1
        inner = s[ob + 1:j - 1] if depth == 0 else s[ob + 1:]
        comma = inner.find(",")
        if comma >= 0:
            parsed.append((btype, inner[:comma].strip(), inner[comma + 1:]))
        i = j if depth == 0 else at + 1
    for btype, key, body in parsed:
        e: Dict[str, Any] = {
            "id": key,
            "type": BIB_TYPE_MAP.get(btype.lower(), "misc"),
        }
        for f in _split_bib_fields(body):
            fm = re.match(r"\s*(\w+)\s*=\s*(.+)$", f, re.S)
            if not fm:
                continue
            key = fm.group(1).lower()
            val = _clean_bib_value(fm.group(2))
            if not val:
                continue
            target = BIB_FIELD_MAP.get(key)
            if not target:
                continue
            if target == "authors":
                e["authors"] = [_clean_bib_value(x) for x in re.split(r"\s+and\s+", val)]
            else:
                e[target] = val
        entries.append(e)
    return entries


RIS_FIELD_MAP = {
    "TY": "type", "TI": "title", "T1": "title", "AU": "authors",
    "A1": "authors", "PY": "year", "Y1": "year", "JO": "journal",
    "JF": "journal", "JA": "journal", "VL": "volume", "IS": "issue",
    "SP": "_start_page", "EP": "_end_page", "DO": "doi", "AB": "abstract",
    "PB": "publisher", "KW": "keywords", "BT": "booktitle",
}
RIS_TYPE_MAP = {
    "JOUR": "article", "BOOK": "book", "THES": "thesis",
    "CONF": "conference", "RPRT": "report", "ELEC": "online",
}


def parse_ris(text: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        mm = re.match(r"^([A-Z0-9]{2})\s*-\s*(.*)$", line)
        if not mm:
            continue
        tag, val = mm.group(1), mm.group(2).strip()
        if tag == "ER":
            if cur:
                sp = cur.pop("_start_page", "")
                ep = cur.pop("_end_page", "")
                if sp:
                    cur["pages"] = f"{sp}-{ep}" if ep else sp
                entries.append(cur)
                cur = None
            continue
        if tag == "TY":
            cur = {"type": RIS_TYPE_MAP.get(val.upper(), "misc")}
            continue
        if cur is None:
            cur = {"type": "misc"}
        target = RIS_FIELD_MAP.get(tag)
        if not target:
            continue
        if target in ("authors", "keywords"):
            cur.setdefault(target, []).append(val)
        else:
            cur[target] = val
    if cur:
        entries.append(cur)
    return entries


def parse_cnki(text: str) -> List[Dict[str, Any]]:
    """
    CNKI 常见的『题名: xxx / 作者: xxx / 来源: xxx / 年份: xxx』逐条文本，
    或以空行分段的关键字段块。缺字段如实留空。
    """
    entries: List[Dict[str, Any]] = []
    key_map = {
        "题名": "title", "篇名": "title", "title": "title",
        "作者": "authors", "author": "authors",
        "来源": "journal", "期刊": "journal", "journal": "journal",
        "年份": "year", "年": "year", "year": "year",
        "卷": "volume", "volume": "volume", "期": "issue", "issue": "issue",
        "页码": "pages", "页": "pages", "pages": "pages",
        "doi": "doi", "DOI": "doi", "摘要": "abstract",
    }
    blocks = re.split(r"\n\s*\n", (text or "").strip())
    for bi, block in enumerate(blocks):
        e: Dict[str, Any] = {"id": f"cnki{bi + 1}", "type": "article"}
        for line in block.splitlines():
            mm = re.match(r"\s*([^:：]+)\s*[:：]\s*(.*)$", line)
            if not mm:
                continue
            k = mm.group(1).strip()
            v = mm.group(2).strip()
            target = key_map.get(k)
            if not target or not v:
                continue
            if target == "authors":
                e["authors"] = [x.strip() for x in re.split(r"[,，;；]", v) if x.strip()]
            else:
                e[target] = v
        if any(e.get(f) for f in ("title", "authors")):
            entries.append(e)
    return entries


def ingest(text: str, fmt: str = "auto") -> Dict[str, Any]:
    """解析文献库原文为结构化 entries；自动检测格式；字段缺失标注，不臆造。"""
    fmt_l = (fmt or "auto").lower()
    if fmt_l == "auto":
        if re.search(r"@\w+\s*\{", text or ""):
            fmt_l = "bibtex"
        elif re.search(r"^\s*(TY|AU|TI|PY)\s*-", text or "", re.M):
            fmt_l = "ris"
        else:
            fmt_l = "cnki"
    parsers = {"bibtex": parse_bibtex, "ris": parse_ris, "cnki": parse_cnki}
    if fmt_l not in parsers:
        return {"status": STATUS_UNCERTAIN, "detected_format": fmt_l,
                "entries": [], "issues": [{"type": "unsupported_format", "format": fmt}],
                "stats": {"parsed_count": 0}}
    entries = parsers[fmt_l](text)
    issues = []
    for i, e in enumerate(entries):
        missing = [k for k in ("title", "authors", "year") if not e.get(k)]
        if missing:
            issues.append({"index": i, "type": "missing_fields", "fields": missing,
                           "message": f"解析条目 #{i} 缺 {missing}，请人工补齐"})
    return {
        "status": STATUS_PARTIAL if issues or not entries else STATUS_OK,
        "detected_format": fmt_l,
        "entries": entries,
        "issues": issues,
        "stats": {"parsed_count": len(entries)},
    }


# ---------------------------------------------------------------------------
# 6) place：引用落点定位（挂得对）
# ---------------------------------------------------------------------------
CLAIM_SIGNALS = (
    "表明 显示 发现 证明 证实 指出 报道 提出 首次 显著 提高 降低 减少 增加 达到 "
    "优于 高于 低于 约为 高达 准确率 精度 召回率 我们 本文 作者"
).split()
# 只认『带单位的数据』或『小数/百分数』；『表1/图2/第3章』这类编号不算数据论断
NUMERIC_SIGNAL = re.compile(r"\d+\.\d+|\d+\s*(?:%|％|倍|℃|mg|km|个|层|口|次)")
REF_NUM = re.compile(r"(?:表|图|式|章|节|段|条)\s*\d+|第\s*\d+\s*[章节段条]")
# 句子切分：中英文句末标点 + 跟随空白。小数点后紧跟数字（18.5）不会被切，避免误断句。
SENT_SPLIT = re.compile(r"(?<=[。；;！!?？.])\s+|\s{2,}")


def _entry_topic_words(e: Dict[str, Any]) -> List[str]:
    blob = " ".join(str(e.get(k, "")) for k in ("title", "abstract", "keywords", "journal"))
    return _content_words(blob)


def place_citations(manuscript: str, entries: List[Dict[str, Any]],
                    max_candidates: int = 3) -> Dict[str, Any]:
    """
    对正文逐句判断：是否需要来源支撑、是否已有引用、建议插入位置与候选文献。
    候选仅来自真实 entries（关键词重叠确定性排序），并标注 needs_review，
    绝不臆造文献；把『整段落末一引』拆到具体论断句是本命令的核心价值。
    """
    manuscript = manuscript or ""  # 畸形输入归一化
    candidates_index = [{"id": str(e.get("id") or f"ref{i + 1}"),
                         "title": e.get("title", ""),
                         "words": set(_entry_topic_words(e))}
                        for i, e in enumerate(entries)]
    sentences: List[Dict[str, Any]] = []
    for lineno, line in enumerate((manuscript or "").splitlines(), 1):
        if not line.strip():
            continue
        for part in SENT_SPLIT.split(line):
            s = part.strip()
            if len(s) < 4:
                continue
            has_cite = bool(CITE_RE.search(s) or AT_RE.search(s))
            words = set(_content_words(s))
            stripped = REF_NUM.sub("", s)  # 去掉图表/章节编号再判数据论断
            numeric = bool(NUMERIC_SIGNAL.search(stripped))
            signal = [w for w in CLAIM_SIGNALS if w in s]
            needs = bool(numeric or signal)
            rank = []
            if needs and words:
                for c in candidates_index:
                    if not c["words"]:
                        continue
                    overlap = len(words & c["words"])
                    if overlap:
                        rank.append({"id": c["id"], "title": c["title"],
                                     "overlap": overlap,
                                     "score": round(overlap / max(1, len(words)), 3)})
                rank.sort(key=lambda x: (-x["score"], -x["overlap"]))
            sentences.append({
                "line": lineno,
                "sentence": s,
                "needs_citation": needs,
                "has_citation": has_cite,
                "signals": signal[:6],
                "has_numeric": numeric,
                "placement": ("covered" if has_cite else ("inline_after_claim" if needs else "none")),
                "candidates": rank[:max_candidates],
                "needs_review": needs and not has_cite,
            })
    needs_cnt = sum(1 for s in sentences if s["needs_citation"])
    covered_cnt = sum(1 for s in sentences if s["has_citation"])
    gap_cnt = sum(1 for s in sentences if s["needs_citation"] and not s["has_citation"])
    return {
        "status": STATUS_OK if not gap_cnt else STATUS_PARTIAL,
        "sentences": sentences,
        "stats": {
            "sentence_count": len(sentences),
            "needs_citation": needs_cnt,
            "already_covered": covered_cnt,
            "citation_gaps": gap_cnt,
        },
        "advice": (
            f"发现 {gap_cnt} 个论断句缺来源支撑；建议把段末集中引用拆分到各论断句后，"
            "并逐条核对候选文献是否真正支撑（候选基于主题词重叠，仅供定位，不作最终判断）。"
            if gap_cnt else "未发现明显缺引的论断句。"
        ),
    }


# ---------------------------------------------------------------------------
# 7) claims：论断核验预筛（对得上：编造线索 / 元数据错配 / 主题错配）
# ---------------------------------------------------------------------------
def _metadata_anomalies(e: Dict[str, Any], idx: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    title = str(e.get("title", "")).strip()
    if len(title) < 5:
        out.append({"type": "title_missing_or_too_short", "index": idx,
                    "detail": f"标题过短或缺失：『{title}』"})
    if not (e.get("authors") or []):
        out.append({"type": "authors_missing", "index": idx, "detail": "作者字段为空"})
    y = _year_of(e)
    if y is None:
        out.append({"type": "year_missing", "index": idx, "detail": "年份缺失或无法解析"})
    elif y < 1800 or y > CURRENT_YEAR + 2:
        out.append({"type": "year_implausible", "index": idx, "detail": f"年份异常：{y}"})
    doi = str(e.get("doi", "")).strip()
    if doi and "/" not in _norm_doi(doi):
        out.append({"type": "doi_malformed", "index": idx, "detail": f"DOI 形态可疑：{doi}"})
    if not any(e.get(f) for f in ("journal", "booktitle", "publisher", "institution", "school")):
        out.append({"type": "source_missing", "index": idx,
                    "detail": "期刊/会议/出版者均为空，难以核验出处"})
    return out


def check_claims(manuscript: str, entries: List[Dict[str, Any]],
                 claims: Optional[List[Dict[str, Any]]] = None,
                 low: float = 0.12, high: float = 0.35) -> Dict[str, Any]:
    """
    确定性预筛（不臆断『编造』）：
      1) 编造线索：条目元数据异常（缺标题/作者/年份、DOI 畸形、无出处）——列needs_review。
      2) 元数据错配：claim 指定 cite_id 时，比对 claim 中的年份/作者姓与条目字段。
      3) 主题错配：claim 文本与所引条目主题词重叠过低 -> suspicious，高 -> plausible。
    输出把需要模型/人工复核的『可疑项』单独列出，逐句判断从 O(n) 降到 O(可疑)。
    """
    manuscript = manuscript or ""  # 畸形输入归一化
    anomalies: List[Dict[str, Any]] = []
    for i, e in enumerate(entries):
        anomalies.extend(_metadata_anomalies(e, i))

    by_id = {str(e.get("id") or f"ref{i + 1}"): e for i, e in enumerate(entries)}
    # 建立 [n] 编号 -> 条目 id 的索引：优先 old_number，其次 new_number，最后按位置
    num_to_id: Dict[str, str] = {}
    for i, e in enumerate(entries):
        eid = str(e.get("id") or f"ref{i + 1}")
        if e.get("old_number") is not None:
            num_to_id[str(e["old_number"])] = eid
        if e.get("new_number") is not None:
            num_to_id[str(e["new_number"])] = eid
        num_to_id.setdefault(str(i + 1), eid)  # 顺序编码制兜底：第 n 条

    item_results: List[Dict[str, Any]] = []
    if claims is None:
        # 未给结构化 claims 时，从正文带引用的句子自动抽取
        claims = []
        for lineno, line in enumerate((manuscript or "").splitlines(), 1):
            for part in SENT_SPLIT.split(line):
                s = part.strip()
                if len(s) >= 6 and (CITE_RE.search(s) or AT_RE.search(s)):
                    cited_ids = []
                    for m in CITE_RE.finditer(s):
                        for n in _expand_citation(m.group(1)):
                            cid = num_to_id.get(str(n))
                            if cid:
                                cited_ids.append(cid)
                    for m in AT_RE.finditer(s):
                        cited_ids.append(m.group(1))
                    claims.append({"text": s, "line": lineno,
                                   "cite_ids": sorted(set(cited_ids))})

    for ci, c in enumerate(claims):
        text = str(c.get("text", ""))
        cids = c.get("cite_ids") or ([c["cite_id"]] if c.get("cite_id") else [])
        words = set(_content_words(text))
        yrs = set(int(y) for y in re.findall(r"(?:19|20)\d{2}", text))
        item = {"index": ci, "text": text[:200], "cite_ids": cids,
                "findings": [], "topic_scores": []}
        for cid in cids:
            e = by_id.get(str(cid))
            if not e:
                item["findings"].append({"type": "cite_target_missing", "cite_id": cid,
                                         "detail": "所引编号在文献库中找不到对应条目"})
                continue
            eyear = _year_of(e)
            if yrs and eyear and eyear not in yrs:
                item["findings"].append({"type": "year_mismatch", "cite_id": cid,
                                         "detail": f"正文年份 {sorted(yrs)} 与条目年份 {eyear} 不符"})
            # 主题词重叠确定性预筛（作者姓比对不作独立判据，避免同名误判）
            ew = set(_entry_topic_words(e))
            overlap = len(words & ew)
            score = round(overlap / max(1, len(words)), 3) if words else 0.0
            verdict = "suspicious" if score < low else ("review" if score < high else "plausible")
            item["topic_scores"].append({"cite_id": cid, "overlap": overlap,
                                         "score": score, "verdict": verdict,
                                         "shared_terms": sorted(list(words & ew))[:8]})
            if verdict == "suspicious":
                item["findings"].append({
                    "type": "topic_mismatch_suspected", "cite_id": cid,
                    "detail": f"主题词重叠度仅 {score}，正文论断与所引文献主题可能不匹配（需人工核对）",
                })
        item["needs_review"] = bool(item["findings"])
        item_results.append(item)

    suspicious = [i for i in item_results if i["needs_review"]]
    return {
        "status": STATUS_OK if not (anomalies or suspicious) else STATUS_PARTIAL,
        "metadata_anomalies": anomalies,
        "claim_results": item_results,
        "suspicious_claims": [i["index"] for i in suspicious],
        "stats": {
            "entries_checked": len(entries),
            "metadata_anomaly_count": len(anomalies),
            "claims_checked": len(item_results),
            "suspicious_claim_count": len(suspicious),
        },
        "note": ("确定性预筛只给线索，不判『编造』；请人工/模型重点复核 suspicious 项，"
                 "其余可按 plausible/review 分档抽查，从而把逐句 O(n) 判断降到 O(可疑)。"),
    }


# ---------------------------------------------------------------------------
# 8) compare：修复前后对照（增益可验证）
# ---------------------------------------------------------------------------
def _problem_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
    ms = payload.get("manuscript", "")
    ents = payload.get("entries", [])
    nf = payload.get("number_field", "new_number")
    v = verify(ms, ents, number_field=nf)
    return {
        "dangling": len(v["dangling_citations"]),
        "uncited": len(v["uncited_entries"]),
        "duplicates": len(v["duplicate_numbers"]),
        "gaps": len(v["numbering_gaps"]),
        "consistent": v["consistent"],
        "order_violations": len(v["order_violations"]),
    }


def compare(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """对同一案例的修复前后做逐项对照，给出可验证的增益证据。"""
    b = _problem_signature(before)
    a = _problem_signature(after)
    metrics = ("dangling", "uncited", "duplicates", "gaps", "order_violations")
    diffs = []
    for k in metrics:
        d = b[k] - a[k]
        diffs.append({"metric": k, "before": b[k], "after": a[k],
                      "delta": -d, "verdict": "improved" if d > 0 else
                      ("regressed" if d < 0 else "unchanged")})
    improved = sum(1 for d in diffs if d["verdict"] == "improved")
    return {
        "status": STATUS_OK,
        "before": b,
        "after": a,
        "diffs": diffs,
        "summary": {
            "improved_metrics": improved,
            "consistent_before": b["consistent"],
            "consistent_after": a["consistent"],
            "verdict": ("增益可验证：修复后问题项减少" if improved else
                        "未见问题项减少，请检查修复动作是否生效"),
        },
    }


# ---------------------------------------------------------------------------
# 9) 全流程
# ---------------------------------------------------------------------------
def pipeline(payload: Dict[str, Any], compact: bool = False) -> Dict[str, Any]:
    """
    payload = {
      "case_id": str,
      "entries": [...],
      "manuscript": str,
      "threshold": float (可选),
      "checks": {"place": bool, "claims": bool, "compare_before": payload(可选)}
    }
    compact=True 时 result 只保留结论与摘要，减少 token 占用（额度节省）。
    """
    entries = payload.get("entries") or []
    manuscript = payload.get("manuscript", "")
    threshold = float(payload.get("threshold", 0.82))
    checks = payload.get("checks") or {}
    do_place = bool(checks.get("place", True))
    do_claims = bool(checks.get("claims", True))

    # 空输入门禁：既无文献条目又无正文时，不得报 success（否则空稿被判为“引用一致”）
    empty_input = (not entries) and (not str(manuscript or "").strip())

    norm = normalize(entries, threshold=threshold)
    ren = renumber(manuscript, norm["entries"], rewrite=True)
    fmt = format_bib(ren["entries"])
    # 一致性核验应基于改写后的正文：若发生了编号改写，用改写稿核验才能真正反映修复结果
    rewritten = ren.get("rewritten_manuscript", manuscript)
    verify_target = rewritten if str(rewritten or "").strip() else manuscript
    ver = verify(verify_target, ren["entries"])
    place = place_citations(verify_target, norm["entries"]) if do_place else None
    claims = check_claims(verify_target, norm["entries"]) if do_claims else None

    statuses = [norm["status"], ren["status"], fmt["status"], ver["status"]]
    if place:
        statuses.append(place["status"])
    if claims:
        statuses.append(claims["status"])
    overall = STATUS_OK
    if STATUS_UNCERTAIN in statuses:
        overall = STATUS_UNCERTAIN
    elif STATUS_PARTIAL in statuses:
        overall = STATUS_PARTIAL
    if empty_input:
        overall = STATUS_PARTIAL

    result: Dict[str, Any] = {
        "bibliography": fmt["references"],
        "number_mapping": ren["mapping"],
        "editable_manuscript": ren.get("rewritten_manuscript", manuscript),
        "input_quality": {
            "empty_input": empty_input,
            "note": ("输入为空：未提供文献条目与正文，未做实质核验，不得视为引用一致"
                     if empty_input else "输入非空"),
        },
        "consistency": {
            "consistent": ver["consistent"],
            "problems": ver["problems"],
            "order_violations": ver["order_violations"],
        },
        "citation_placement": ({
            "stats": place["stats"], "advice": place["advice"],
            "gaps": [s["sentence"] for s in place["sentences"]
                     if s["needs_citation"] and not s["has_citation"]][:20],
        } if place else None),
        "claim_check": ({
            "stats": claims["stats"],
            "suspicious_claims": claims["suspicious_claims"],
            "metadata_anomalies": claims["metadata_anomalies"][:20],
            "note": claims["note"],
        } if claims else None),
        "evidence": {
            "dedup_decisions": norm["decisions"],
            "dedup_issues": norm["issues"],
            "unresolved_citations": ren["unresolved"],
            "rewrite_changes": ren.get("rewrite_changes", []),
        },
    }

    summary_lines = [
        f"去重：{norm['stats']['input_count']}→{norm['stats']['output_count']} 条"
        f"（合并 {norm['stats']['merged_count']}）",
        f"编号：{len(ren['mapping'])} 条，悬空 {len(ver['dangling_citations'])}、"
        f"未引 {len(ver['uncited_entries'])}、连续={'是' if not ver['numbering_gaps'] else '否'}",
        f"一致性：{'通过' if ver['consistent'] else '有问题'}",
    ]
    if place:
        summary_lines.append(f"落点：缺引论断句 {place['stats']['citation_gaps']}")
    if claims:
        summary_lines.append(
            f"论断：元数据异常 {claims['stats']['metadata_anomaly_count']}、"
            f"可疑论断 {claims['stats']['suspicious_claim_count']}"
        )
    result["summary"] = "；".join(summary_lines)

    if compact:
        result = {
            "status": overall,
            "summary": result["summary"],
            "bibliography": result["bibliography"],
            "input_quality": result["input_quality"],
            "consistency": result["consistency"],
            "citation_placement": result["citation_placement"],
            "claim_check": result["claim_check"],
        }

    out: Dict[str, Any] = {
        "case_id": payload.get("case_id", ""),
        "status": overall,
    }
    # 紧凑模式不输出体积大的 pipeline 子步骤容器；普通模式保留旧结构向后兼容
    if not compact:
        out["pipeline"] = {
            "normalize": norm,
            "renumber": ren,
            "format": fmt,
            "verify": ver,
            **({"place": place} if place else {}),
            **({"claims": claims} if claims else {}),
        }
    out["result"] = result
    if checks.get("compare_before"):
        out["comparison"] = compare(checks["compare_before"],
                                    {"manuscript": manuscript, "entries": ren["entries"]})
    return out


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

    sp = sub.add_parser("ingest")
    sp.add_argument("input", help="文本文件或 JSON {text, format}")
    sp.add_argument("--format", default="auto", choices=["auto", "bibtex", "ris", "cnki"])

    sp = sub.add_parser("renumber")
    sp.add_argument("input", help="JSON：含 manuscript 与 entries")
    sp.add_argument("--id-field", default="id")
    sp.add_argument("--no-rewrite", action="store_true", help="不输出改写正文")

    sp = sub.add_parser("format")
    sp.add_argument("input", help="JSON：含 entries")
    sp.add_argument("--number-field", default="new_number")
    sp.add_argument("--standard", default="gb7714", choices=["gb7714", "apa"])

    sp = sub.add_parser("verify")
    sp.add_argument("input", help="JSON：含 manuscript 与 entries")
    sp.add_argument("--number-field", default="new_number")

    sp = sub.add_parser("place")
    sp.add_argument("input", help="JSON：含 manuscript 与 entries")
    sp.add_argument("--max-candidates", type=int, default=3)

    sp = sub.add_parser("claims")
    sp.add_argument("input", help="JSON：含 manuscript/entries，可选 claims")
    sp.add_argument("--low", type=float, default=0.12)
    sp.add_argument("--high", type=float, default=0.35)

    sp = sub.add_parser("compare")
    sp.add_argument("input", help="JSON：含 before 与 after 两个 {manuscript, entries}")

    sp = sub.add_parser("pipeline")
    sp.add_argument("input", help="JSON：case_id/entries/manuscript")
    sp.add_argument("--compact", action="store_true", help="紧凑摘要模式，省 token")

    args = p.parse_args(argv)
    data = _load_json_arg(args.input)

    if args.cmd == "normalize":
        entries = data.get("entries", data) if isinstance(data, dict) else data
        out = normalize(entries, threshold=args.threshold)
    elif args.cmd == "ingest":
        if isinstance(data, dict):
            text, fmt = data.get("text", ""), data.get("format", args.format)
        else:
            text, fmt = str(data), args.format
        out = ingest(text, fmt=fmt)
    elif args.cmd == "renumber":
        out = renumber(data.get("manuscript", ""), data.get("entries", []),
                       id_field=args.id_field, rewrite=not args.no_rewrite)
    elif args.cmd == "format":
        out = format_bib(data.get("entries", []), number_field=args.number_field,
                         standard=args.standard)
    elif args.cmd == "verify":
        out = verify(data.get("manuscript", ""), data.get("entries", []),
                     number_field=args.number_field)
    elif args.cmd == "place":
        out = place_citations(data.get("manuscript", ""), data.get("entries", []),
                              max_candidates=args.max_candidates)
    elif args.cmd == "claims":
        out = check_claims(data.get("manuscript", ""), data.get("entries", []),
                           claims=data.get("claims"), low=args.low, high=args.high)
    elif args.cmd == "compare":
        out = compare(data.get("before", {}), data.get("after", {}))
    elif args.cmd == "pipeline":
        out = pipeline(data, compact=args.compact)
    else:
        p.error("未知命令")
        return 2

    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
