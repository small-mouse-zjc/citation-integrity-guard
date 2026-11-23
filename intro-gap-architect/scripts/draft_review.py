#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""draft_review.py — 引言成稿的四问核验

不生成成稿，只检查 Agent 已经写出的 `introduction_draft`：
  立得住：背景是否空转、是否有具体锚点；
  分得清：相关工作是否有分组与比较维度；
  说得实：空白是否由 >=2 篇已引文献的局限推出；
  对得上：引用是否都能映射到 works，贡献是否带证据锚点。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from intro_engine import detect_hype, group_matrix, coverage, _first_author, _year_of
except Exception:  # 允许从仓库根目录直接跑
    from scripts.intro_engine import detect_hype, group_matrix, coverage, _first_author, _year_of  # type: ignore

SECTION_PATTERNS = {
    "background": r"(研究背景|选题背景|引言背景|Background|Introduction)",
    "related": r"(相关工作|文献综述|研究现状|Related\s+Work|Literature\s+Review)",
    "gap": r"(研究空白|研究缺口|未解决问题|问题定义|Research\s+Gap|Gap)",
    "contribution": r"(本文贡献|主要贡献|贡献表述|本文工作|Contributions?|Our\s+Work)",
}

CITE_PATTERNS = [
    r"\[([A-Za-z][A-Za-z0-9_:\-]{0,40})\]",          # [w1] / [smith2020]
    r"\[(\d{1,3}(?:[,，\-–]\s*\d{1,3})*)\]",          # [1,2]
    r"\\cite[a-zA-Z]*\{([^}]+)\}",                    # \cite{key}
    r"\(([A-Z][A-Za-z'’\-]+(?:\s+et\s+al\.)?,\s*\d{4}[a-z]?)\)",  # (Smith, 2020)
]

HYPE_WORDS = r"(近年来|随着.{0,12}的(?:快速)?发展|受到广泛关注|具有重要意义|蓬勃发展|方兴未艾|日益重要|越来越重要|重大突破)"


def split_sections(draft: str) -> Dict[str, str]:
    lines = draft.replace("\r\n", "\n").splitlines()
    sections: Dict[str, List[str]] = {"background": [], "related": [], "gap": [], "contribution": [], "other": []}
    current = "other"
    for ln in lines:
        m = re.match(r"^\s*(#{1,6})\s+(.*)$", ln)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip().strip("*")
            matched = None
            for key, pat in SECTION_PATTERNS.items():
                if re.search(pat, title, re.I):
                    matched = key
                    break
            if matched:
                current = matched
                sections[current].append(ln)
            elif current != "other" and level >= 2:
                # 组内小标题：继续归入当前四部件
                sections[current].append(ln)
            else:
                current = "other"
                sections[current].append(ln)
        elif re.match(r"^\s*\*\*[^*]{2,30}\*\*\s*$", ln):
            title = ln.strip().strip("*")
            matched = None
            for key, pat in SECTION_PATTERNS.items():
                if re.search(pat, title, re.I):
                    matched = key
                    break
            if matched:
                current = matched
            sections[current].append(ln)
        else:
            sections[current].append(ln)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def norm_works(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    works = case.get("works") or case.get("references") or case.get("literature") or []
    if isinstance(works, dict):
        works = works.get("works") or works.get("items") or []
    if not works and case.get("text"):
        from intro_engine import _parse_bibtex, _parse_ris
        fmt = str(case.get("format", "lines")).lower()
        text = str(case.get("text", ""))
        if fmt in ("bibtex", "bib"):
            works = _parse_bibtex(text)
        elif fmt == "ris":
            works = _parse_ris(text)
    out = []
    for i, w in enumerate(works if isinstance(works, list) else [], 1):
        if not isinstance(w, dict):
            continue
        out.append(dict(w, id=str(w.get("id") or w.get("key") or w.get("citation_key") or f"w{i}")))
    return out


def work_index(works: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for w in works:
        keys = [str(w.get("id", "")), str(w.get("key", "")), str(w.get("citation_key", ""))]
        if w.get("title"):
            keys.append(re.sub(r"\W+", "", str(w["title"]))[:24].lower())
        fa = _first_author(w)
        yr = _year_of(w)
        if fa and yr:
            keys.append(f"{fa.lower()}{yr}")
            keys.append(f"{fa.lower()},{yr}")
        for k in keys:
            if k:
                idx[k.lower()] = w
    return idx


def extract_citations(text: str) -> List[str]:
    out: List[str] = []
    for pat in CITE_PATTERNS:
        for m in re.finditer(pat, text):
            raw = m.group(1)
            for part in re.split(r"[,，;；]", raw):
                if part.strip():
                    out.append(part.strip())
    return out


def resolve_citation(tok: str, idx: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    t = tok.lower().strip()
    if t in idx:
        return idx[t]
    return idx.get(re.sub(r"\s+", "", t))


def review(draft: str, works: List[Dict[str, Any]], case_id: str = "") -> Dict[str, Any]:
    sections = split_sections(draft)
    violations: List[Dict[str, Any]] = []

    def add(type_: str, severity: str, detail: str, excerpt: str = ""):
        violations.append({"type": type_, "severity": severity, "detail": detail, "excerpt": excerpt[:200]})

    # 1) 四部件齐全
    for key, label in (("background", "研究背景"), ("related", "相关工作"), ("gap", "研究空白"), ("contribution", "贡献表述")):
        if not sections.get(key) or len(re.sub(r"^#+\s*.*$", "", sections[key], flags=re.M).strip()) < 30:
            add("section_missing", "critical", f"缺少或过短：{label}")

    # 2) 引用解析
    all_cites = extract_citations(draft)
    idx = work_index(works)
    unknown = [c for c in all_cites if not resolve_citation(c, idx)]
    for c in unknown[:12]:
        add("citation_unmapped", "critical", f"引用 {c} 无法映射到 works 中的任何条目", c)
    cited_ids = set()
    for c in all_cites:
        w = resolve_citation(c, idx)
        if w:
            cited_ids.add(str(w.get("id")))

    if works:
        for w in works:
            if str(w.get("id")) not in cited_ids:
                add("work_uncited", "warning", f"文献 {w.get('id')} 未在成稿中被引用", str(w.get('id')))

    # 3) 背景空转
    bg = sections.get("background", "")
    if bg:
        h = detect_hype(bg)
        if not h.get("holds_up"):
            for s in h.get("hype_sentences", [])[:4]:
                add("background_hype", "major", "背景句空转/无具体锚点", s)
        if h.get("concrete_anchor_count", 0) < 2:
            add("background_unanchored", "major", "背景具体锚点少于 2 个（领域/问题/约束）", bg)

    # 4) 相关工作分组
    rel = sections.get("related", "")
    if rel:
        subheads = re.findall(r"(?m)^\s*#{2,6}\s+.+|^\s*\*\*[^*]{2,40}\*\*\s*$", rel)
        if len(subheads) < 2:
            add("related_ungrouped", "major", "相关工作没有 >=2 个分组标题，可能仍是流水账", rel)
        if len(extract_citations(rel)) < 3:
            add("related_thin", "warning", "相关工作引用少于 3 条，覆盖可能不足", rel)
        # 同一维度比较词
        if not re.search(r"(相比|相较于|不同于|compared|whereas|however|共同|均|both|但|然而|区别|差异|取舍|权衡)", rel, re.I):
            add("related_no_comparison", "warning", "相关工作缺少比较/取舍表述", rel)

    # 5) 空白推导
    gap = sections.get("gap", "")
    if gap:
        if len(extract_citations(gap)) < 2:
            add("gap_unsupported", "critical", "研究空白段引用少于 2 条，无法由已引文献推出", gap)
        if not re.search(r"(局限|限制|不足|尚未|未能|缺乏|空白|gap|limitation|remain|not\s+yet)", gap, re.I):
            add("gap_no_limitation", "major", "空白段没有明确指向已有工作的局限/未覆盖场景", gap)
        if not re.search(r"(本文|本研究|我们|本工作|this\s+(?:study|work|paper))", gap, re.I):
            add("gap_no_link", "warning", "空白段未说明本文工作如何填补", gap)

    # 6) 贡献对齐
    contrib = sections.get("contribution", "")
    if contrib:
        bullets = re.findall(r"(?m)^\s*(?:[-*•]|\d+[.)、])\s+(.+)$", contrib)
        if len(bullets) < 2:
            add("contribution_thin", "major", "贡献条目少于 2 条", contrib)
        for b in bullets:
            if len(b) < 25:
                add("contribution_vague", "warning", "贡献条目过短/不可核对", b)
            if re.search(r"(首次|首个|率先|first\s+to|novel)", b, re.I) and not re.search(r"(图|表|Fig|Table|§|section|实验|结果|evidence)", b, re.I):
                add("contribution_overclaim", "major", "出现“首次/首个”但未给图表/实验锚点", b)
            if not re.search(r"(图|表|Fig|Table|实验|结果|方法|数据集|§|section|evidence|\[)", b, re.I):
                add("contribution_no_anchor", "warning", "贡献条目没有图表/实验/方法锚点", b)

    critical = [v for v in violations if v["severity"] == "critical"]
    major = [v for v in violations if v["severity"] == "major"]
    gate = "fail" if critical else ("review" if major else "pass")
    return {
        "case_id": case_id,
        "status": "ok" if gate == "pass" else "needs_attention",
        "gate": gate,
        "sections": {k: len(v) for k, v in sections.items()},
        "counts": {"critical": len(critical), "major": len(major),
                   "warning": len([v for v in violations if v["severity"] == "warning"])},
        "violations": violations,
        "citations": {"total": len(all_cites), "unmapped": unknown,
                      "cited_work_ids": sorted(cited_ids), "works_total": len(works)},
        "metrics": {"draft_chars": len(draft), "paragraphs": len([p for p in draft.split("\n\n") if p.strip()]),
                    "works": len(works)},
        "note": "只做结构与引用映射；转述忠实度、空白是否真成立、贡献是否夸大仍需 Agent 回原文核对。",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="引言成稿四问核验")
    ap.add_argument("--draft", required=True)
    ap.add_argument("--case", required=True, help="case.json（含 works/references）")
    ap.add_argument("--out", default=None)
    ap.add_argument("--outdir", default=None,
                    help="把 Agent 写好的引言与核验结果落盘，并写入 artifacts")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    draft = Path(args.draft).read_text(encoding="utf-8", errors="replace")
    works = norm_works(case)
    r = review(draft, works, str(case.get("case_id") or case.get("id") or ""))
    if args.outdir:
        outdir = Path(args.outdir).resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        draft_path = outdir / "introduction_draft.md"
        draft_path.write_text(draft, encoding="utf-8")
        review_path = outdir / "draft_review.json"
        review_path.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        r["artifacts"] = {"draft": str(draft_path), "review": str(review_path), "outdir": str(outdir)}
    text = json.dumps(r, ensure_ascii=False, indent=None if args.json else 2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

