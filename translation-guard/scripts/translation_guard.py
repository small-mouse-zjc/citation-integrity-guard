#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translation_guard.py — 确定性科研文献翻译守门引擎
====================================================
面向「文献翻译」挑战。翻译措辞由模型完成；本引擎把易错的四个动作固化为确定性脚本：

四问对应（题面原文）：
  术语稳 —— build_glossary / lock_terms / check_terms：抽取术语、全篇锁定译名、
            并验证标题/正文/图注/结论译法一致（术语表真正被执行，不是写在提示里）。
  段落全 —— segment / align：按语义边界切段、稳定段号、跨页续段标记、
            原文—译文段落级一一对应，检出漏段/重复/错位。
  关系准 —— protect / restore / verify：翻译前把数字/单位/公式/引用标记/化学式/
            否定与限定词抽成占位符保护，翻译后回填并核对有无丢失或篡改。
  可核验 —— evidence / verify：每段译文回指原文段号与译法依据，译不准的显式标注。

设计约束：
  - 纯标准库、无网络、无第三方依赖，Python 3.8+ 可运行。
  - 不替代模型做翻译，只做"翻译前保护 / 翻译后核验"的确定性部分。
  - 所有判定可回溯，不确定项进 needs_review，不臆造术语译名或译文。

中间表示（translation JSON）：
{
  "case_id": "示例", "source_lang": "en", "target_lang": "zh",
  "paragraphs": [
    {"id":"P1","section":"Abstract","text":"...","kind":"body"}
  ],
  "glossary": [{"source":"carbonate","target":"碳酸盐岩","scope":"global"}],
  "translations": {"P1":"..."}   # 可选：模型译文，用于核验类子命令
}

子命令：
  build_glossary  从原文抽取术语候选（英文/中文短语、缩略语），合并人工术语表
  lock_terms      把术语表编译成"锁定提示串"供模型翻译时强制使用
  segment         切段/编号/跨页续段/重复段检测
  protect         翻译前：把数字单位/公式/引用/化学式/否定限定词替换为占位符
  restore         翻译后：回填占位符，核对有无丢失/篡改
  align           段落级对齐，检出漏段/重复/错位
  check_terms     译名一致性：同一源术语是否用了统一译名
  verify          关系核验：数字/单位/否定/限定/引用/公式是否保留
  evidence        每段译文的原文定位与译法依据
  pipeline        全流程串联，--compact 省 token

用法见 examples/minimal_example.md。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

STATUS_OK = "success"
STATUS_PARTIAL = "partial"
STATUS_UNCERTAIN = "needs_review"

# 需保护元素模式（翻译前后必须一致）
UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|％|mD|md|kg|km2|km²|km|cm|mm|μm|um|nm|℃|°C|GPa|MPa|Pa|"
    r"mg|μg|g|mL|L|mmol|mol|ms|min|h|s|yr|years?|倍|次|层|口|个|m)(?![A-Za-z])", re.I)
# 公式在句号/分号/逗号处截断，不跨句
FORMULA_RE = re.compile(r"[A-Za-zα-ωΑ-Ω][A-Za-z0-9α-ωΑ-Ω_^]*\s*=\s*[^。；;，,.]{2,40}")
CITE_RE = re.compile(r"\[(\d+(?:\s*[,，]\s*\d+)*(?:\s*[-–]\s*\d+)?)\]|\[@[A-Za-z0-9_\-:]+\]")
CHEM_RE = re.compile(r"\b(?:CO2|CO₂|H2O|H₂O|CH4|CH₄|NaCl|SiO2|SiO₂|CaCO3|CaCO₃|Fe2O3|Fe₂O₃|SO4|SO₄)\b")
NEG_WORDS = ["not", "no", "never", "neither", "nor", "without", "hardly",
             "不", "未", "无", "非", "没有", "并非", "不能", "无法"]
LIMIT_WORDS = ["only", "mainly", "primarily", "approximately", "about", "significantly",
               "slightly", "may", "might", "likely", "suggest", "possible",
               "仅", "主要", "约", "大约", "显著", "略微", "可能", "表明", "提示", "倾向于"]

# 术语抽取停用词
STOP = set("""the a an of and or in on for to with by is are was were be been being this that
these those we our their its it as at from into using used use based which who whom whose
can could would should may might will shall have has had do does did not no than then thus
there here where when while of on in at to for from by with without between among via per
的 了 和 与 及 在 是 为 对 中 该 这 其 并 等 也 而 从 以 于 上 下 将 把 被 通过 基于 我们 本文 作者""".split())


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return re.sub(r"\s+", " ", s).strip()


def _as_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {"paragraphs": []}
    return data


def _paragraphs(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    return p.get("paragraphs") or []


def _get(p: Dict[str, Any], key: str, default=""):
    if not isinstance(p, dict):
        return default
    return p.get(key, default)


# ---------------------------------------------------------------------------
# 1) 术语稳：抽取 / 锁定 / 一致性
# ---------------------------------------------------------------------------
def _term_candidates(text: str, lang: str) -> List[str]:
    """抽术语候选：首字母大写词组、缩略语、连字符术语、中文名词短语。"""
    cands = []
    # 英文缩略语（全大写，2-8字母）
    for m in re.finditer(r"\b[A-Z]{2,8}\b", text):
        w = m.group(0)
        if w not in STOP:
            cands.append(w)
    # 英文词组：连续的首字母大写词（可能含小写连接词）
    for m in re.finditer(r"\b(?:[A-Z][a-z]+\s+){1,3}[A-Z]?[a-z]*", text):
        phrase = m.group(0).strip()
        words = [w for w in phrase.split() if w.lower() not in STOP and len(w) > 2]
        if len(words) >= 2:
            cands.append(" ".join(words))
    # 连字符术语
    for m in re.finditer(r"\b[a-z]+(?:-[a-z]+)+\b", text, re.I):
        cands.append(m.group(0))
    # 中文术语：2-6 字连续汉字，去停用词片段
    for m in re.finditer(r"[\u4e00-\u9fff]{2,6}", text):
        w = m.group(0)
        if w not in STOP and w not in ("本文", "我们", "作者", "研究", "表明", "结果"):
            cands.append(w)
    # 去重保序
    seen, out = set(), []
    for c in cands:
        k = _norm(c)
        if k and k not in seen:
            seen.add(k); out.append(c.strip())
    return out


def build_glossary(payload: Dict[str, Any], min_freq: int = 2) -> Dict[str, Any]:
    """从原文抽术语候选（按全篇频次过滤），合并人工术语表。"""
    paras = _paragraphs(payload)
    counter = Counter()
    where: Dict[str, set] = defaultdict(set)
    for para in paras:
        for t in _term_candidates(para.get("text", ""), _get(payload, "source_lang", "en")):
            counter[_norm(t)] += 1
            where[_norm(t)].add(para.get("id", ""))
    manual = payload.get("glossary") or []
    manual_norm = {_get(g, "source", ""): g for g in manual if isinstance(g, dict)}
    candidates = []
    for norm, cnt in counter.most_common():
        if cnt < min_freq and norm not in manual_norm:
            continue
        src = next((t for t in _term_candidates(" ".join(p.get("text", "") for p in paras), "en")
                    if _norm(t) == norm), norm)
        g = manual_norm.get(norm)
        candidates.append({
            "source": _get(g, "source", src) if g else src,
            "target": _get(g, "target", "") if g else "",
            "scope": _get(g, "scope", "global") if g else "global",
            "frequency": cnt,
            "paragraphs": sorted(where[norm]),
            "locked": bool(g and _get(g, "target", "")),
        })
    # 人工表里没在原文出现的也保留
    for norm, g in manual_norm.items():
        if norm not in {_norm(c["source"]) for c in candidates}:
            candidates.append({"source": _get(g, "source", ""), "target": _get(g, "target", ""),
                               "scope": _get(g, "scope", "global"), "frequency": 0,
                               "paragraphs": [], "locked": bool(_get(g, "target", ""))})
    unlocked = [c for c in candidates if not c["locked"]]
    return {
        "status": STATUS_PARTIAL if unlocked else STATUS_OK,
        "glossary": candidates,
        "needs_review": [c["source"] for c in unlocked],
        "stats": {"candidate_count": len(candidates),
                  "locked_count": len(candidates) - len(unlocked),
                  "unlocked_count": len(unlocked)},
        "note": "候选术语需人工确认译名后写入 glossary.target；未锁定的不强制替换。",
    }


def lock_terms(payload: Dict[str, Any]) -> Dict[str, Any]:
    """把术语表编译成锁定提示串，供模型翻译时强制使用。"""
    glossary = payload.get("glossary") or []
    locked = [g for g in glossary if isinstance(g, dict) and _get(g, "source") and _get(g, "target")]
    lines = []
    for g in locked:
        scope = _get(g, "scope", "global")
        lines.append(f"- {_get(g,'source')} → {_get(g,'target')} (scope={scope})")
    # 一致性约束声明
    rules = [
        "术语表内每个源术语必须全程使用指定译名，不得同义替换。",
        "数字、单位、公式、文献编号、化学式按原样保留（由占位符保护）。",
        "标题、摘要、正文、图注、结论中出现同一术语时译名一致。",
    ]
    return {
        "status": STATUS_OK if locked else STATUS_UNCERTAIN,
        "lock_prompt": "【术语锁定表（强制）】\n" + "\n".join(lines) + "\n\n【约束】\n" +
                       "\n".join(f"{i+1}. {r}" for i, r in enumerate(rules)),
        "locked_terms": [{"source": _get(g, "source"), "target": _get(g, "target")} for g in locked],
        "stats": {"locked_count": len(locked), "total_glossary": len(glossary)},
    }


def check_terms(payload: Dict[str, Any]) -> Dict[str, Any]:
    """译名一致性：同一源术语在译文里是否出现多个不同译名。"""
    glossary = payload.get("glossary") or []
    translations = payload.get("translations") or {}
    # 对每个锁定术语，检查其目标译名是否出现；检测是否有同一术语被译成多个候选
    issues = []
    usage = defaultdict(lambda: defaultdict(list))
    for g in glossary:
        if not isinstance(g, dict):
            continue
        src = _get(g, "source"); tgt = _get(g, "target")
        if not src or not tgt:
            continue
        for pid, zh in translations.items():
            if tgt in zh:
                usage[src][tgt].append(pid)
            # 检测源术语的其它可能译法（同义词表）
            for alt in _get(g, "variants", []) or []:
                if alt and alt != tgt and alt in zh:
                    usage[src][alt].append(pid)
    for src, variants in usage.items():
        if len(variants) > 1:
            issues.append({"type": "inconsistent_term", "source": src,
                           "variants": {k: v for k, v in variants.items()},
                           "decision": "needs_review"})
    # 未使用的锁定术语（可能漏译该术语）
    unused = []
    for g in glossary:
        if isinstance(g, dict) and _get(g, "source") and _get(g, "target"):
            if g["source"] not in usage:
                unused.append(g["source"])
    return {
        "status": STATUS_OK if not issues else STATUS_PARTIAL,
        "issues": issues,
        "unused_locked_terms": unused,
        "term_usage": {k: {kk: vv for kk, vv in v.items()} for k, v in usage.items()},
        "stats": {"inconsistent_count": len(issues), "unused_count": len(unused)},
    }


# ---------------------------------------------------------------------------
# 2) 段落全：切段 / 对齐
# ---------------------------------------------------------------------------
def segment(payload: Dict[str, Any]) -> Dict[str, Any]:
    """稳定段号 + 跨页续段 + 重复段检测。"""
    paras = _paragraphs(payload)
    segs = []
    seen_text: Dict[str, str] = {}
    dup = []
    for i, para in enumerate(paras):
        text = str(para.get("text", ""))
        pid = str(para.get("id") or f"P{i+1}")
        key = _norm(text)
        rec = {"id": pid, "index": i + 1, "section": para.get("section", ""),
               "kind": para.get("kind", "body"), "page": para.get("page"),
               "text": text, "char_count": len(text)}
        # 跨页/跨栏续段：上段末无句末标点 且 本段首为小写/无大写 → 疑似续段
        if i > 0:
            prev = str(paras[i-1].get("text", "")).strip()
            prev_open = not re.search(r"[。；：.!?？:：;]\s*$", prev)
            starts_lower = bool(re.match(r"[a-z，、；）)]", text.strip()))
            if prev_open and starts_lower:
                rec["continuation_of"] = str(paras[i-1].get("id") or f"P{i}")
        if key in seen_text and key:
            dup.append({"id": pid, "duplicate_of": seen_text[key]})
        else:
            seen_text[key] = pid
        segs.append(rec)
    return {
        "status": STATUS_PARTIAL if (dup or any("continuation_of" in s for s in segs)) else STATUS_OK,
        "segments": segs,
        "duplicates": dup,
        "continuations": [{"id": s["id"], "of": s["continuation_of"]}
                          for s in segs if "continuation_of" in s],
        "stats": {"segment_count": len(segs), "duplicate_count": len(dup),
                  "continuation_count": sum(1 for s in segs if "continuation_of" in s)},
    }


def align(payload: Dict[str, Any]) -> Dict[str, Any]:
    """原文段号 ↔ 译文段号一一对应，检出漏段/重复/错位。"""
    seg = payload.get("segments") or [s["id"] for s in segment(payload)["segments"]]
    translations = payload.get("translations") or {}
    src_ids = [str(s) for s in seg]
    zh_ids = [str(k) for k in translations.keys()]
    missing = [i for i in src_ids if i not in zh_ids]
    extra = [i for i in zh_ids if i not in src_ids]
    # 顺序错位：译文顺序与原文顺序不一致
    common = [i for i in src_ids if i in zh_ids]
    zh_common = [i for i in zh_ids if i in src_ids]
    out_of_order = [(i, j) for i, j in zip(common, zh_common) if i != j]
    problems = []
    if missing:
        problems.append(f"漏段：{missing}")
    if extra:
        problems.append(f"多余/错位段号：{extra}")
    if out_of_order:
        problems.append(f"段号顺序错位共 {len(out_of_order)} 处")
    return {
        "status": STATUS_OK if not problems else STATUS_PARTIAL,
        "aligned": [{"id": i, "translated": i in zh_ids} for i in src_ids],
        "missing": missing, "extra": extra,
        "out_of_order_count": len(out_of_order),
        "problems": problems,
        "stats": {"source_segments": len(src_ids), "translated": len(zh_ids),
                  "coverage": round(len(common) / max(1, len(src_ids)), 4)},
    }


# ---------------------------------------------------------------------------
# 3) 关系准：保护 / 回填 / 核验
# ---------------------------------------------------------------------------
def _protect_one(text: str, prefix: str) -> Tuple[str, List[Dict[str, Any]]]:
    """把一段文本里的需保护元素替换为占位符，返回(保护文本, tokens)。"""
    tokens: List[Dict[str, Any]] = []
    protected = text

    def repl(pattern, kind):
        nonlocal protected
        def sub(m):
            raw = m.group(0)
            ph = f"⟦{prefix}_{len(tokens):03d}⟧"
            tokens.append({"placeholder": ph, "kind": kind, "raw": raw})
            return ph
        protected = pattern.sub(sub, protected)

    repl(CHEM_RE, "chemical")
    repl(FORMULA_RE, "formula")
    repl(CITE_RE, "citation")
    repl(UNIT_RE, "number_unit")
    return protected, tokens


def protect(payload: Dict[str, Any]) -> Dict[str, Any]:
    """翻译前：对每段抽取需保护元素，产出带占位符的待译文本。"""
    paras = _paragraphs(payload)
    out = []
    for para in paras:
        pid = str(para.get("id", ""))
        protected, tokens = _protect_one(str(para.get("text", "")), pid)
        out.append({"id": pid, "protected_text": protected, "tokens": tokens})
    return {
        "status": STATUS_OK,
        "protected": out,
        "instruction": "把 protected_text 交给模型翻译；占位符 ⟦...⟧ 必须原样保留，不得翻译或改写。",
        "stats": {"paragraphs": len(out),
                  "tokens": sum(len(x["tokens"]) for x in out),
                  "by_kind": dict(Counter(t["kind"] for x in out for t in x["tokens"]))},
    }


def restore(payload: Dict[str, Any]) -> Dict[str, Any]:
    """翻译后：回填占位符，核对丢失/篡改。"""
    protected = payload.get("protected") or []
    translations = payload.get("translations") or {}
    restored = {}
    problems = []
    all_direct = []
    for item in protected:
        pid = str(item.get("id", ""))
        zh = str(translations.get(pid, ""))
        tokens = item.get("tokens", [])
        text = zh
        preserved_direct = []
        for t in tokens:
            ph = t["placeholder"]
            if ph in text:
                text = text.replace(ph, t["raw"])
            elif t["raw"] and t["raw"] in text:
                # 占位符未用，但原文值直接出现在译文里 → 视为直接保留（不算错误）
                preserved_direct.append(t["raw"])
                all_direct.append(t["raw"])
            else:
                problems.append({"type": "placeholder_lost", "id": pid,
                                 "placeholder": ph, "expected_raw": t["raw"],
                                 "detail": "译文丢失占位符且原文值未出现，该数字/公式/引用可能被改写或删除"})
        # 残留未识别占位符
        leftover = re.findall(r"⟦[^⟧]+⟧", text)
        if leftover:
            problems.append({"type": "placeholder_unknown", "id": pid, "leftover": leftover})
        restored[pid] = text
    return {
        "status": STATUS_OK if not problems else STATUS_PARTIAL,
        "restored": restored,
        "problems": problems,
        "preserved_direct": all_direct,
        "stats": {"paragraphs": len(protected), "issues": len(problems),
                  "preserved_direct_count": len(all_direct)},
    }


def verify(payload: Dict[str, Any]) -> Dict[str, Any]:
    """关系核验：数字/单位/否定/限定/引用/公式是否保留。"""
    paras = _paragraphs(payload)
    translations = payload.get("translations") or {}
    issues = []
    per_para = []
    for para in paras:
        pid = str(para.get("id", ""))
        src = str(para.get("text", ""))
        zh = str(translations.get(pid, ""))
        if not zh:
            issues.append({"type": "missing_translation", "id": pid})
            continue
        checks = {}
        # 数字（含小数）是否全部保留
        src_nums = re.findall(r"\d+(?:\.\d+)?", src)
        zh_nums = re.findall(r"\d+(?:\.\d+)?", zh)
        missing_nums = [n for n in src_nums if n not in zh_nums]
        checks["numbers"] = {"source_count": len(src_nums), "kept": not missing_nums,
                             "missing": missing_nums}
        if missing_nums:
            issues.append({"type": "number_lost", "id": pid, "missing": missing_nums})
        # 引用标记
        src_cites = [m.group(0) for m in CITE_RE.finditer(src)]
        missing_cites = [c for c in src_cites if c not in zh]
        checks["citations"] = {"kept": not missing_cites, "missing": missing_cites}
        if missing_cites:
            issues.append({"type": "citation_lost", "id": pid, "missing": missing_cites})
        # 否定词：原文有否定而译文完全无对应 → 提示
        src_neg = [w for w in NEG_WORDS if re.search(r"\b" + re.escape(w) + r"\b", src, re.I)]
        zh_neg = [w for w in NEG_WORDS if w in zh]
        checks["negation"] = {"source": src_neg, "in_translation": zh_neg,
                              "kept": bool(src_neg) == bool(zh_neg)}
        if src_neg and not zh_neg:
            issues.append({"type": "negation_maybe_lost", "id": pid, "source_neg": src_neg})
        # 限定词
        src_lim = [w for w in LIMIT_WORDS if re.search(r"\b" + re.escape(w) + r"\b", src, re.I)]
        zh_lim = [w for w in LIMIT_WORDS if w in zh]
        checks["limitation"] = {"source": src_lim, "in_translation": zh_lim,
                                "kept": bool(src_lim) == bool(zh_lim)}
        if src_lim and not zh_lim:
            issues.append({"type": "limitation_maybe_lost", "id": pid, "source_lim": src_lim})
        # 化学式
        src_chem = [m.group(0) for m in CHEM_RE.finditer(src)]
        missing_chem = [c for c in src_chem if c not in zh]
        checks["chemicals"] = {"kept": not missing_chem, "missing": missing_chem}
        if missing_chem:
            issues.append({"type": "chemical_lost", "id": pid, "missing": missing_chem})
        per_para.append({"id": pid, "checks": checks})
    needs = [i for i in issues if "maybe" in i["type"]]
    return {
        "status": STATUS_OK if not issues else (STATUS_UNCERTAIN if not [i for i in issues if "maybe" not in i["type"]] else STATUS_PARTIAL),
        "consistent": not issues,
        "per_paragraph": per_para,
        "issues": issues,
        "needs_review": [i["id"] for i in needs],
        "stats": {"paragraphs": len(paras), "issue_count": len(issues),
                  "needs_review_count": len(needs)},
        "note": "数字/引用/化学式丢失为硬错误；否定/限定词为'疑似丢失'，需人工确认。",
    }


# ---------------------------------------------------------------------------
# 4) 可核验：证据
# ---------------------------------------------------------------------------
def evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """每段译文的原文定位 + 译法依据。"""
    paras = _paragraphs(payload)
    translations = payload.get("translations") or {}
    glossary = payload.get("glossary") or []
    ev = []
    for para in paras:
        pid = str(para.get("id", ""))
        src = str(para.get("text", ""))
        zh = str(translations.get(pid, ""))
        basis = []
        # 术语依据
        for g in glossary:
            if isinstance(g, dict) and _get(g, "source") and _get(g, "target"):
                if _get(g, "source") in src:
                    basis.append({"type": "glossary", "source": _get(g, "source"),
                                  "target": _get(g, "target")})
        # 保护元素依据
        _, tokens = _protect_one(src, pid)
        for t in tokens:
            basis.append({"type": "protected:" + t["kind"], "raw": t["raw"]})
        ev.append({
            "id": pid,
            "source_location": {"section": para.get("section", ""), "page": para.get("page"),
                                "paragraph_id": pid},
            "source_head": src[:60],
            "translation_head": zh[:60],
            "basis": basis,
            "translated": bool(zh),
            "needs_review": not bool(zh),
        })
    return {
        "status": STATUS_OK if all(e["translated"] for e in ev) else STATUS_PARTIAL,
        "evidence": ev,
        "stats": {"paragraphs": len(ev), "with_basis": sum(1 for e in ev if e["basis"])},
    }


# ---------------------------------------------------------------------------
# 5) 全流程
# ---------------------------------------------------------------------------
def pipeline(payload: Dict[str, Any], compact: bool = False) -> Dict[str, Any]:
    p = _as_payload(payload)
    seg = segment(p)
    gloss = build_glossary(p)
    lock = lock_terms(p)
    prot = protect(p)
    # 若有译文，把保护元素清单注入 restore 输入做回填核对
    restore_input = {"protected": prot["protected"], "translations": p.get("translations") or {}}
    rest = restore(restore_input)
    align_res = align(p)
    term_res = check_terms(p)
    ver = verify(p)
    ev = evidence(p)

    statuses = [s["status"] for s in (seg, gloss, lock, rest, align_res, term_res, ver, ev)]
    overall = STATUS_OK
    if STATUS_UNCERTAIN in statuses:
        overall = STATUS_UNCERTAIN
    elif STATUS_PARTIAL in statuses:
        overall = STATUS_PARTIAL
    has_trans = bool(p.get("translations"))
    trans_map = p.get("translations") or {}
    if not has_trans:
        overall = STATUS_PARTIAL  # 只交核验表、不交真实译文 = 未完成主产物
    trans_items = []
    for i, para in enumerate(_paragraphs(p)):
        pid = str(para.get("id") or f"P{i+1}")
        src = str(para.get("text", ""))
        tgt = str(trans_map.get(pid, "") or "")
        trans_items.append({
            "id": pid,
            "index": i + 1,
            "section": para.get("section", ""),
            "page": para.get("page"),
            "source": src,
            "target": tgt,
            "translated": bool(tgt.strip()),
            "basis": ("目标语译文" if tgt.strip() else "待译"),
        })
    translated_count = sum(1 for x in trans_items if x["translated"])
    untranslated_ids = [x["id"] for x in trans_items if not x["translated"]]

    result = {
        "segment_count": seg["stats"]["segment_count"],
        "glossary_locked": gloss["stats"]["locked_count"],
        "protected_tokens": prot["stats"]["tokens"],
        "restore_issues": rest["stats"]["issues"],
        "aligned_coverage": align_res["stats"]["coverage"],
        "term_inconsistencies": term_res["stats"]["inconsistent_count"],
        "verification": {"consistent": ver["consistent"], "issues": ver["issues"],
                         "needs_review": ver["needs_review"]},
        "evidence_index": ev["evidence"],
        "lock_prompt": lock["lock_prompt"],
        "protected_for_translation": prot["protected"],
        "translations": trans_items,
        "bilingual": [{"id": x["id"], "source": x["source"], "target": x["target"]} for x in trans_items],
        "translation_metrics": {
            "total": len(trans_items),
            "translated": translated_count,
            "untranslated": len(trans_items) - translated_count,
            "coverage": round(translated_count / max(1, len(trans_items)), 3),
            "untranslated_ids": untranslated_ids,
        },
        "summary": (
            f"段 {seg['stats']['segment_count']}；术语锁定 {gloss['stats']['locked_count']}/"
            f"{gloss['stats']['candidate_count']}；保护元素 {prot['stats']['tokens']}"
            f"（公式{prot['stats']['by_kind'].get('formula',0)}/"
            f"引用{prot['stats']['by_kind'].get('citation',0)}/"
            f"数字{prot['stats']['by_kind'].get('number_unit',0)}）；"
            f"译文 {translated_count}/{len(trans_items)} 段；"
            f"核验问题 {ver['stats']['issue_count']}（待确认{ver['stats']['needs_review_count']}）"
        ),
    }
    out = {"case_id": _get(p, "case_id"), "status": overall,
           "has_translations": has_trans}
    if not compact:
        out["pipeline"] = {"segment": seg, "glossary": gloss, "lock": lock,
                           "protect": prot, "restore": rest, "align": align_res,
                           "check_terms": term_res, "verify": ver, "evidence": ev}
    out["result"] = result
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load(path: str):
    if path == "-":
        import sys as _s
        return json.load(_s.stdin)
    return json.load(open(path, "r", encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="确定性科研文献翻译守门引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("build_glossary", "lock_terms", "segment", "protect", "align",
              "check_terms", "verify", "evidence", "pipeline"):
        sp = sub.add_parser(c); sp.add_argument("input")
        if c == "build_glossary":
            sp.add_argument("--min-freq", type=int, default=2)
        if c == "pipeline":
            sp.add_argument("--compact", action="store_true")
    args = ap.parse_args(argv)
    data = _load(args.input)
    p = _as_payload(data)
    if args.cmd == "build_glossary":
        out = build_glossary(p, min_freq=args.min_freq)
    elif args.cmd == "lock_terms":
        out = lock_terms(p)
    elif args.cmd == "segment":
        out = segment(p)
    elif args.cmd == "protect":
        out = protect(p)
    elif args.cmd == "align":
        out = align(p)
    elif args.cmd == "check_terms":
        out = check_terms(p)
    elif args.cmd == "verify":
        out = verify(p)
    elif args.cmd == "evidence":
        out = evidence(p)
    elif args.cmd == "pipeline":
        out = pipeline(p, compact=args.compact)
    else:
        ap.error("未知命令"); return 2
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
