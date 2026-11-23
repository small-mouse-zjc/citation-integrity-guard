#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""polish_audit.py — 学术语言润色的保源核验器

设计目标（对应题面四问）：
  改得对：逐句对齐，给出原文—改文—修改类型—理由的核验底稿；
  说得像：术语表强制回扫、语域/口语化提示；
  没改坏：数字、单位、引用、否定、限定强度、图表指向必须守恒；
  讲得清：所有违规带原文句、改文句、定位与判定依据。

只做确定性检查，不代替模型润色。Agent 必须先写出真实改文，再跑本脚本。
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

FULLWIDTH = str.maketrans("０１２３４５６７８９．，％：；（）［］", "0123456789.,%:;()[]")

ABBREV = ["e.g.", "i.e.", "et al.", "etc.", "vs.", "Fig.", "Figs.", "Eq.", "Eqs.",
          "No.", "Dr.", "Prof.", "approx.", "ca.", "cf.", "al.", "Eds.", "Ed."]

HEDGES = [
    r"\bmay\b", r"\bmight\b", r"\bcould\b", r"\bwould\b", r"\bcan\b",
    r"\bsuggest(?:s|ed|ing)?\b", r"\bindicat(?:e|es|ed|ing)\b",
    r"\bappear(?:s|ed|ing)?\b", r"\bseem(?:s|ed|ing)?\b",
    r"\blikely\b", r"\bprobably\b", r"\bpossibly\b", r"\bperhaps\b",
    r"\bpotentially\b", r"\bpresumably\b", r"\barguably\b",
    r"\btend(?:s|ed)?\s+to\b", r"\bin\s+principle\b", r"\bto\s+our\s+knowledge\b",
    r"\bwe\s+(?:believe|argue|suggest|hypothesize)\b",
    r"可能", r"或许", r"也许", r"似乎", r"看来", r"推测", r"估计", r"有望",
    r"倾向于", r"我们认为", r"据我们所知", r"初步", r"尚不", r"有待", r"大致",
]

BOOSTERS = [
    r"\bdemonstrat(?:e|es|ed|ing)\b", r"\bprove(?:s|d|n)?\b",
    r"\bestablish(?:es|ed|ing)?\b", r"\bconfirm(?:s|ed|ing)?\b",
    r"\bclearly\s+show(?:s|ed|n)?\b", r"\bundoubtedly\b", r"\bcertainly\b",
    r"\bobviously\b", r"\bdefinitely\b", r"\balways\b", r"\bnever\b",
    r"证明", r"证实", r"表明", r"无疑", r"必然", r"显然", r"毫无疑问", r"完全", r"始终", r"从未",
]

NEGATIONS = [
    r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bnone\b", r"\bneither\b", r"\bnor\b",
    r"\bcannot\b", r"\bcan't\b", r"\bd(?:oes|id|o)n't\b", r"\bisn't\b",
    r"\baren't\b", r"\bwasn't\b", r"\bweren't\b", r"\bwithout\b",
    r"\bfail(?:s|ed)?\s+to\b", r"\black(?:s|ed)?\b", r"\babsence\s+of\b",
    r"不", r"未", r"无", r"非", r"没有", r"无法", r"尚未", r"并非", r"缺乏",
]

# 限定词分档：任一分档在原文出现、改文消失，就说明断言强度被改变。
HEDGE_CLASSES = {
    "possibility": [r"\bmay\b", r"\bmight\b", r"\bcould\b", r"\bcan\b", r"\bpossibly\b",
                    r"\bperhaps\b", r"\bpotentially\b", r"可能", r"或许", r"也许", r"有望"],
    "inference": [r"\bsuggest(?:s|ed|ing)?\b", r"\bindicat(?:e|es|ed|ing)\b",
                  r"\bappear(?:s|ed|ing)?\b", r"\bseem(?:s|ed|ing)?\b", r"\blikely\b",
                  r"\bprobably\b", r"\bpresumably\b", r"\barguably\b", r"提示", r"表明", r"似乎", r"看来", r"推测", r"估计"],
    "author_stance": [r"\bwe\s+(?:believe|argue|suggest|hypothesize)\b", r"\bto\s+our\s+knowledge\b",
                      r"\bin\s+principle\b", r"我们认为", r"据我们所知", r"理论上", r"初步"],
    "condition": [r"\btend(?:s|ed)?\s+to\b", r"倾向于", r"尚不", r"有待", r"大致"],
}

NEGATION_CLASSES = {
    "neg": [r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bnone\b", r"\bneither\b", r"\bnor\b",
            r"\bd(?:oes|id|o)n't\b", r"\bisn't\b", r"\baren't\b", r"\bwasn't\b", r"\bweren't\b",
            r"不", r"未", r"无", r"非", r"没有", r"尚未", r"并非"],
    "cannot": [r"\bcannot\b", r"\bcan't\b", r"无法"],
    "without": [r"\bwithout\b", r"缺乏"],
    "lack": [r"\bfail(?:s|ed)?\s+to\b", r"\black(?:s|ed)?\b", r"\babsence\s+of\b"],
}

CITATION_PATTERNS = [
    r"\[[0-9][0-9,\-–—\s]*\]",
    r"【[^】]{1,60}】",
    r"\\cite[a-zA-Z]*\{[^}]+\}",
    r"\([A-Z][A-Za-z'’\-]+(?:\s+et\s+al\.)?(?:,\s*|\s+)\d{4}[a-z]?(?:;\s*[A-Z][A-Za-z'’\-]+(?:\s+et\s+al\.)?(?:,\s*|\s+)\d{4}[a-z]?)*\)",
    r"[A-Z][A-Za-z'’\-]+\s+et\s+al\.?\s*\(?\d{4}\)?",
]

CONTRACTIONS = re.compile(r"\b(?:isn't|aren't|wasn't|weren't|don't|doesn't|didn't|can't|won't|it's|that's|there's|we're|they're|I'm)\b", re.I)
INFORMAL = re.compile(r"\b(?:a lot of|lots of|stuff|things|get|got|kind of|sort of|pretty|really|totally|huge|big time)\b", re.I)


def norm(s: str) -> str:
    s = s.translate(FULLWIDTH)
    s = (s.replace("’", "'").replace("“", '"').replace("”", '"')
         .replace("–", "-").replace("—", "-").replace("\u00a0", " "))
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def paragraphs(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.split(r"\n\s*\n", text.strip())
    if len(raw) == 1:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # 单换行：标题必须和下一行合并，避免把 "# Abstract" 当成独立段落
        groups: List[str] = []
        i = 0
        while i < len(lines):
            if lines[i].startswith("#") or (len(lines[i]) < 80 and i + 1 < len(lines)):
                groups.append((lines[i] + "\n" + lines[i + 1]).strip() if i + 1 < len(lines) else lines[i])
                i += 2
            else:
                groups.append(lines[i])
                i += 1
        if len(groups) > 1:
            raw = groups
    return [p.strip() for p in raw if p.strip()]


def sentences(paragraph: str) -> List[str]:
    s = norm(paragraph)
    # 保护小数点和常见缩写中的句点
    s = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", s)
    for ab in ABBREV:
        s = s.replace(ab, ab.replace(".", "<DOT>"))
    # 保护 URL / DOI
    s = re.sub(r"https?://\S+", lambda m: m.group(0).replace(".", "<DOT>"), s)
    parts = re.findall(r"[^。！？!?\.]+[。！？!?\.]+|[^。！？!?\.]+$", s)
    out = []
    for p in parts:
        p = p.replace("<DOT>", ".").strip()
        if p:
            out.append(p)
    return out


def mask_citations(text: str) -> Tuple[str, List[str]]:
    found: List[str] = []

    def repl(m):
        found.append(m.group(0))
        return " [CIT] "

    s = text
    for pat in CITATION_PATTERNS:
        s = re.sub(pat, repl, s)
    return s, found


def extract_numbers(text: str) -> List[Dict[str, str]]:
    masked, _ = mask_citations(norm(text))
    # 去掉 DOI/URL 中的数字噪声
    masked = re.sub(r"https?://\S+|10\.\d{4,9}/\S+", " ", masked)
    pat = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)*(?:\s*[%‰])?(?:\s*(?:±|~|–|-|to|至)\s*[-+]?\d+(?:[.,]\d+)*)?")
    out = []
    for m in pat.finditer(masked):
        raw = m.group(0).strip()
        if not raw:
            continue
        out.append({"raw": raw, "key": number_key(raw), "context": masked[max(0, m.start() - 40):m.end() + 20].strip()})
    return out


def number_key(raw: str) -> str:
    s = raw.translate(FULLWIDTH).replace(" ", "")
    s = s.replace("，", ",").replace("％", "%").replace("‰", "‰")
    # 千分位：1,234 -> 1234；但 1,2 这种范围不处理
    if re.fullmatch(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?", s):
        s = s.replace(",", "")
    s = s.replace("–", "-").replace("—", "-").replace("~", "-").replace("至", "-").replace("to", "-")
    parts = [p for p in re.split(r"(?<=\d)-(?=[-+]?\d)|±", s) if p]
    norm_parts = []
    for p in parts:
        p = p.strip("%‰")
        try:
            norm_parts.append(format(float(p), "g"))
        except Exception:
            norm_parts.append(p)
    return "-".join(norm_parts)


def extract_citations(text: str) -> List[str]:
    _, found = mask_citations(norm(text))
    return [re.sub(r"\s+", "", f) for f in found]


def find_terms(text: str, termbase: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out = []
    for row in termbase:
        src = row.get("source", "")
        tgt = row.get("target", "")
        forbidden = row.get("forbidden", "")
        if not src:
            continue
        hit = bool(re.search(re.escape(src), text, re.I if re.search(r"[A-Za-z]", src) else 0))
        out.append({"source": src, "target": tgt, "forbidden": forbidden, "source_present": hit,
                    "target_present": bool(tgt) and bool(re.search(re.escape(tgt), text, re.I if re.search(r"[A-Za-z]", tgt) else 0))})
    return out


def load_termbase(path: Optional[str]) -> List[Dict[str, str]]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("terms") or data.get("glossary") or []
        out = []
        for x in data:
            if isinstance(x, dict):
                out.append({"source": str(x.get("source") or x.get("term") or ""),
                            "target": str(x.get("target") or x.get("translation") or ""),
                            "forbidden": ";".join(x.get("forbidden") or x.get("variants") or [])})
        return out
    rows = []
    with p.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({"source": (r.get("source") or r.get("source_term") or "").strip(),
                         "target": (r.get("target") or r.get("target_term") or "").strip(),
                         "forbidden": (r.get("forbidden") or r.get("forbidden_variants") or "").strip()})
    return [r for r in rows if r["source"]]


def has_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def sentence_pairs(src_sents: List[str], rev_sents: List[str]) -> List[Dict[str, Any]]:
    pairs = []
    if len(src_sents) == len(rev_sents):
        for i, (a, b) in enumerate(zip(src_sents, rev_sents), 1):
            pairs.append({"index": i, "source": a, "revised": b,
                          "ratio": round(difflib.SequenceMatcher(None, a, b).ratio(), 3)})
        return pairs
    sm = difflib.SequenceMatcher(None, [norm(x) for x in src_sents], [norm(x) for x in rev_sents])
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                a, b = src_sents[i1 + k], rev_sents[j1 + k]
                pairs.append({"index": i1 + k + 1, "source": a, "revised": b,
                              "ratio": round(difflib.SequenceMatcher(None, a, b).ratio(), 3)})
        else:
            for k in range(i1, i2):
                a = src_sents[k]
                best = None
                best_r = 0.0
                for j in range(j1, j2):
                    r = difflib.SequenceMatcher(None, a, rev_sents[j]).ratio()
                    if r > best_r:
                        best, best_r = j, r
                pairs.append({"index": k + 1, "source": a,
                              "revised": rev_sents[best] if best is not None else "",
                              "ratio": round(best_r, 3)})
    return pairs


def audit(source: str, revised: str, termbase: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    termbase = termbase or []
    src_paras = paragraphs(source)
    rev_paras = paragraphs(revised)
    src_sents_all = [s for p in src_paras for s in sentences(p)]
    rev_sents_all = [s for p in rev_paras for s in sentences(p)]
    violations: List[Dict[str, Any]] = []

    def add(type_: str, severity: str, detail: str, source_excerpt: str = "", revised_excerpt: str = "", location: str = ""):
        violations.append({"type": type_, "severity": severity, "detail": detail,
                           "source_excerpt": source_excerpt[:180], "revised_excerpt": revised_excerpt[:180],
                           "location": location})

    # 1) 段落完整性
    if len(rev_paras) < len(src_paras):
        delta = len(src_paras) - len(rev_paras)
        add("paragraph_dropped", "critical" if delta > 1 else "major",
            f"原文 {len(src_paras)} 段，改文 {len(rev_paras)} 段，少 {delta} 段")
    for i in range(min(len(src_paras), len(rev_paras))):
        ratio = difflib.SequenceMatcher(None, norm(src_paras[i]), norm(rev_paras[i])).ratio()
        if len(src_paras[i]) > 50 and ratio < 0.25:
            add("heavy_rewrite", "major", f"第 {i+1} 段改动过大（相似度 {ratio:.2f}），可能超出润色范围", src_paras[i], rev_paras[i], f"paragraph:{i+1}")
        elif len(src_paras[i]) > 50 and ratio < 0.40:
            add("large_rewrite", "warning", f"第 {i+1} 段改动较大（相似度 {ratio:.2f}），请确认未改变原意", src_paras[i], rev_paras[i], f"paragraph:{i+1}")

    # 2) 数字守恒
    src_nums = extract_numbers(source)
    rev_nums = extract_numbers(revised)
    rev_num_keys = {n["key"] for n in rev_nums}
    src_num_keys = {}
    for n in src_nums:
        src_num_keys.setdefault(n["key"], n)
    for k, n in src_num_keys.items():
        if k not in rev_num_keys:
            add("number_missing", "critical", f"原文数字 {n['raw']} 在改文中缺失或被改值", n["context"], "", "number")
    if len(rev_num_keys - set(src_num_keys)) > 0:
        for k in sorted(rev_num_keys - set(src_num_keys))[:6]:
            add("new_number", "warning", f"改文新增原文没有的数字 {k}，须确认不是补造", "", "", "number")

    # 3) 引用守恒
    src_cites = extract_citations(source)
    rev_cites = extract_citations(revised)
    rev_cite_set = set(rev_cites)
    for c in sorted(set(src_cites)):
        if c not in rev_cite_set:
            add("citation_missing", "critical", f"原文引用标记 {c} 在改文中缺失或被改写", c, "", "citation")
    for c in sorted(set(rev_cites) - set(src_cites))[:6]:
        add("citation_added", "warning", f"改文新增引用标记 {c}，须确认来源真实", "", c, "citation")

    # 4) 否定与限定强度
    pairs = sentence_pairs(src_sents_all, rev_sents_all)
    for p in pairs:
        a, b = p["source"], p["revised"]
        src_neg = {k for k, pats in NEGATION_CLASSES.items() if has_any(a, pats)}
        rev_neg = {k for k, pats in NEGATION_CLASSES.items() if has_any(b, pats)}
        missing_neg = src_neg - rev_neg
        if missing_neg:
            add("negation_dropped", "critical", "原文否定/排除关系在改文中丢失（缺失类型：%s）" % ",".join(sorted(missing_neg)), a, b, f"sentence:{p['index']}")
        src_hedge = {k for k, pats in HEDGE_CLASSES.items() if has_any(a, pats)}
        rev_hedge = {k for k, pats in HEDGE_CLASSES.items() if has_any(b, pats)}
        missing_hedge = src_hedge - rev_hedge
        if missing_hedge:
            add("hedge_dropped", "critical", "原文限定/不确定性在改文中被去掉（缺失类型：%s），断言强度被抬高" % ",".join(sorted(missing_hedge)), a, b, f"sentence:{p['index']}")
        if b and not has_any(a, BOOSTERS) and has_any(b, BOOSTERS):
            add("booster_added", "major", "改文新增了原文没有的强断言词", a, b, f"sentence:{p['index']}")

    # 5) 术语表
    terms = find_terms(source, termbase)
    for t in terms:
        if not t["source_present"]:
            continue
        if t["target"] and not t["target_present"]:
            add("term_missing", "major", f"术语 {t['source']} 的锁定译名/写法 {t['target']} 未在改文出现", t["source"], "", "term")
        for bad in [x.strip() for x in re.split(r"[;,；，]", t["forbidden"]) if x.strip()]:
            if re.search(re.escape(bad), revised, re.I if re.search(r"[A-Za-z]", bad) else 0):
                add("term_forbidden", "major", f"改文出现术语禁用变体 {bad}（应统一为 {t['target'] or t['source']}）", t["source"], bad, "term")

    # 6) 标题/编号/图表指向
    for pat, name in [(r"(?m)^#{1,6}\s+.+$", "heading"), (r"\b(?:Fig(?:ure)?|Table|Eq(?:uation)?|图|表|式)\s*[0-9A-Za-z]+", "figure_ref")]:
        src_hits = set(re.findall(pat, source))
        rev_hits = set(re.findall(pat, revised))
        for h in sorted(src_hits - rev_hits):
            add(f"{name}_missing", "major" if name == "heading" else "warning",
                f"原文结构/指向 {h.strip()} 在改文中缺失", h, "", name)

    # 7) 语域提示（不判失败）
    style_notes = []
    if CONTRACTIONS.search(revised):
        style_notes.append("改文含英文缩写形式（如 isn't/don't），正式学术语域建议展开。")
    if INFORMAL.search(revised):
        style_notes.append("改文含口语化表达（a lot/stuff/get 等），建议改为书面语。")
    if re.search(r"\b(?:very|really|extremely|totally|obviously)\b", revised, re.I):
        style_notes.append("改文含强化副词，若非原文所有，建议弱化以避免夸大。")

    # 8) 句数/长度指标
    metrics = {
        "source_chars": len(source), "revised_chars": len(revised),
        "length_ratio": round(len(revised) / max(1, len(source)), 3),
        "source_paragraphs": len(src_paras), "revised_paragraphs": len(rev_paras),
        "source_sentences": len(src_sents_all), "revised_sentences": len(rev_sents_all),
        "avg_source_sentence_len": round(sum(len(s) for s in src_sents_all) / max(1, len(src_sents_all)), 1),
        "avg_revised_sentence_len": round(sum(len(s) for s in rev_sents_all) / max(1, len(rev_sents_all)), 1),
        "edit_ratio": round(1 - difflib.SequenceMatcher(None, norm(source), norm(revised)).ratio(), 3),
        "numbers_source": len(src_nums), "numbers_revised": len(rev_nums),
        "citations_source": len(src_cites), "citations_revised": len(rev_cites),
    }

    critical = [v for v in violations if v["severity"] == "critical"]
    major = [v for v in violations if v["severity"] == "major"]
    gate = "fail" if critical else ("review" if major else "pass")
    status = {"pass": "ok", "review": "needs_attention", "fail": "needs_attention"}[gate]
    return {
        "status": status,
        "gate": gate,
        "metrics": metrics,
        "violations": violations,
        "counts": {"critical": len(critical), "major": len(major),
                   "warning": len([v for v in violations if v["severity"] == "warning"])},
        "preserved": {
            "numbers": [n["raw"] for n in src_nums],
            "citations": sorted(set(src_cites)),
            "hedges": sorted({h for s in src_sents_all for h in _matched(s, HEDGES)}),
            "terms": [t["source"] for t in terms if t["source_present"]],
        },
        "sentence_pairs": pairs,
        "style_notes": style_notes,
        "note": "本审计只做确定性守恒检查；措辞质量、学术性、原意忠实度仍需 Agent 逐句复核。",
    }


def _matched(text: str, patterns: List[str]) -> List[str]:
    out = []
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            out.append(m.group(0))
    return out


def ledger(text: str, termbase: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    return {
        "paragraphs": len(paragraphs(text)),
        "sentences": [{"index": i + 1, "text": s} for i, s in enumerate(sentences(text))],
        "numbers": extract_numbers(text),
        "citations": extract_citations(text),
        "hedges": sorted({h for s in sentences(text) for h in _matched(s, HEDGES)}),
        "boosters": sorted({h for s in sentences(text) for h in _matched(s, BOOSTERS)}),
        "negations": sorted({h for s in sentences(text) for h in _matched(s, NEGATIONS)}),
        "headings": [x.strip() for x in re.findall(r"(?m)^#{1,6}\s+.+$", text)],
        "figure_refs": re.findall(r"\b(?:Fig(?:ure)?|Table|Eq(?:uation)?|图|表|式)\s*[0-9A-Za-z]+", text),
        "terms": find_terms(text, termbase or []),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="学术润色保源核验")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("ledger", help="抽取事实台账")
    l.add_argument("--input", required=True)
    l.add_argument("--termbase", default=None)
    l.add_argument("--out", default=None)
    c = sub.add_parser("check", help="核对原文与改文")
    c.add_argument("--source", required=True, help="原文文件，或 - 从 stdin 读")
    c.add_argument("--revised", required=True, help="改文文件，或 - 从 stdin 读")
    c.add_argument("--termbase", default=None)
    c.add_argument("--out", default=None)
    c.add_argument("--outdir", default=None,
                   help="把润色后的正文与核验结果落盘，并写入 artifacts")
    c.add_argument("--json", action="store_true", help="输出紧凑 JSON")
    args = ap.parse_args(argv)

    def read(p: str) -> str:
        if p == "-":
            return sys.stdin.read()
        return Path(p).read_text(encoding="utf-8", errors="replace")

    tb = load_termbase(args.termbase)
    if args.cmd == "ledger":
        res = ledger(read(args.input), tb)
    else:
        source_text = read(args.source)
        revised_text = read(args.revised)
        res = audit(source_text, revised_text, tb)
        if args.outdir:
            outdir = Path(args.outdir).resolve()
            outdir.mkdir(parents=True, exist_ok=True)
            polished = outdir / "polished.md"
            polished.write_text(revised_text, encoding="utf-8")
            audit_json = outdir / "polish_audit.json"
            audit_json.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            res["artifacts"] = {"polished_md": str(polished),
                                "audit_json": str(audit_json),
                                "outdir": str(outdir)}
    text = json.dumps(res, ensure_ascii=False, indent=None if args.json else 2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
