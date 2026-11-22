#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
polish_engine.py — 学术语言润色守门/完成引擎
====================================================
面向「学术语言润色」挑战。润色措辞由模型完成；本引擎把题面四问里最容易出错、
且可以确定性执行的动作固化成脚本：

  改得对 —— detect_grammar：只标高置信度的硬错误（重复词、句首小写、标点重复、
            中英粘连、the the、双冠词等），不替模型重写整段，避免"换种说法掩盖错误"。
  说得像 —— check_terms / check_register：术语全篇一致性回扫 + 语域诊断（口语化、
            绝对化、宣传化、人称误用），让术语表真正被执行、语体贴合目标载体。
  没改坏 —— protect / check_preserve：把数字单位、引用编号、图表指向、公式、化学式、
            限定词、否定词抽成守护清单；润色前后逐项核对，限定强度被加强/削弱即告警。
  讲得清 —— segment / evidence / render_draft：逐句切分，逐句给"原文—改文—修改类型—
            理由—守护依据—核验结论"，第三方可据此判断这处该不该改。

完成器：solve(case_path, out_dir) 从真实 case 出发，适配材料 → 全流程 → 渲染可编辑
润色成稿草稿 → 装配 /app/output/result.json 并回执 delivery。无真实润色文本的句标
〔待润色〕，绝不臆造润色措辞或术语译法。

设计约束：纯标准库、无网络、无第三方依赖，Python 3.8+ 可运行；所有判定可回溯；
不确定项进 needs_review，不臆造。

中间表示（polish JSON）：
{
  "case_id": "示例",
  "target_register": "journal",            # journal/thesis/grant/rebuttal/abstract
  "source_lang": "en",                     # en/zh/mixed
  "paragraphs": [
    {"id":"P1","section":"Abstract","kind":"body","text":"原文段落"}
  ],
  "glossary": [{"source":"porosity","target":"porosity","scope":"global"}],
  "polished": {"P1":"模型润色后的完整段落文本"}   # 可选，核验类子命令用
}

子命令：
  segment / protect / detect_grammar / check_terms / check_register /
  check_preserve / verify / evidence / pipeline / render-draft / solve
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

# ---- 守护元素模式（润色前后必须保持一致）----
# 数字 + 单位/百分号；单位表刻意覆盖常见学术单位
UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|％|mD|md|kg|km2|km²|km|cm|mm|μm|um|nm|℃|°C|GPa|MPa|Pa|"
    r"mg|μg|g|mL|L|mmol|mol|ms|min|h|s|yr|years?|倍|次|层|口|个|m)(?![A-Za-z])", re.I)
# 裸数字（含小数、负号、科学计数）——用于没有单位的数值守护
NUM_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])")
# 引用编号 [1] / [1,2] / [1-3] / [@key]
CITE_RE = re.compile(r"\[(\d+(?:\s*[,，]\s*\d+)*(?:\s*[-–]\s*\d+)?)\]|\[@[A-Za-z0-9_\-:]+\]")
# 图表指向 Fig. 2 / Figure 3 / 表 4 / Table 2 / Eq. (1) / 式(2)
REFMARK_RE = re.compile(
    r"(?:Fig\.?|Figure|Tab\.?|Table|Eq\.?|Equation|式|图|表)\s*\(?\d+[a-zA-Z]?\)?", re.I)
# 公式 x = ... 或 L = -Σ...
FORMULA_RE = re.compile(r"[A-Za-zα-ωΑ-Ω][A-Za-z0-9α-ωΑ-Ω_^²³¹⁰-⁹₀-₉]*\s*=\s*[^\s。；;，,、：:！!？?（）【】\[\]\"“”‘’]{1,40}")
# 化学式（ASCII 边界判定，避免中文文献误判）
CHEM_RE = re.compile(
    r"(?<![A-Za-z0-9₀-₉])(?:H2SO4|H₂SO₄|CO2|CO₂|H2O|H₂O|CH4|CH₄|NaCl|SiO2|SiO₂|"
    r"CaCO3|CaCO₃|Fe2O3|Fe₂O₃|SO4|SO₄)(?![A-Za-z0-9])")
# 缩写/小写连字符词，切句时不作为句末
ABBREV = {"e.g", "i.e", "etc", "vs", "Fig", "Tab", "Eq", "Dr", "Prof", "No", "cf", "et al"}

# 限定词：强度/范围/确定性；分档用于守恒核验
LIMIT_SCALE = {
    # 弱化/不确定（原文有则改文须保留，不能删）
    "may": -1, "might": -1, "could": -1, "possible": -1, "possibly": -1,
    "likely": -1, "suggest": -1, "suggests": -1, "indicate": -1, "tend": -1,
    "approximately": -1, "about": -1, "roughly": -1, "slightly": -1,
    "部分": -1, "可能": -1, "或许": -1, "倾向于": -1, "表明": -1, "提示": -1,
    "约": -1, "大约": -1, "主要": -1, "一定程度上": -1,
    # 强/绝对（原文没有则改文不应新增，新增即"偷偷加强"）
    "always": 2, "never": 2, "definitely": 2, "certainly": 2, "proves": 2,
    "prove": 2, "undoubtedly": 2, "absolutely": 2, "must": 2,
    "一定": 2, "必然": 2, "绝对": 2, "证实": 2, "毫无疑问": 2, "必定": 2,
    # 中性限定（范围/数量）
    "only": 1, "mainly": 1, "primarily": 1, "significantly": 1,
    "仅": 1, "只": 1, "唯一": 1, "显著": 1,
}
# 否定词
NEG_WORDS = ["not", "no", "never", "neither", "nor", "without", "hardly", "cannot",
             "不", "未", "无", "非", "没有", "并非", "不能", "无法", "否"]
# 语域诊断词：口语化 / 绝对化 / 宣传化 / 人称误用
COLLOQUIAL = ["a lot of", "lots of", "stuff", "thing", "kind of", "sort of", "got",
              "get", "big", "huge", "really", "very", "basically", "actually", "quite",
              "很多", "东西", "挺", "非常", "基本上", "其实", "相当"]
ABSOLUTIST = ["always", "never", "definitely", "certainly", "obviously", "clearly",
              "proves", "proven", "it is clear that", "no doubt", "absolute",
              "一定", "必然", "绝对", "显然", "毫无疑问", "证明了"]
PROMOTIONAL = ["revolutionary", "groundbreaking", "cutting-edge", "novel", "unique",
               "excellent", "perfect", "world-class", "state-of-the-art", "amazing",
               "革命性", "开创性", "世界一流", "完美", "极佳", "独一无二"]
FIRST_PERSON = ["I ", "we ", "my ", "our ", "I've", "we've", "我", "我们", "本文作者"]
STOP = set("""the a an of and or in on for to with by is are was were be been being this that
these those we our their its it as at from into using used use based which who whom whose
can could would should may might will shall have has had do does did not no than then thus
there here where when while per via between among 的 了 和 与 及 在 是 为 对 中 该 这 其 并 等 也 而 从 以 于 上 下 将 把 被 通过 基于""".split())


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", str(s or "")).strip()


def _as_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    return data if isinstance(data, dict) else {}


def _get(p: Dict[str, Any], key: str, default: Any = "") -> Any:
    v = p.get(key, default)
    return default if v is None else v


def _paragraphs(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for i, para in enumerate(_get(p, "paragraphs", []) or []):
        if isinstance(para, dict):
            d = dict(para)
            d.setdefault("id", f"P{i+1}")
            out.append(d)
        elif isinstance(para, str):
            out.append({"id": f"P{i+1}", "section": "", "kind": "body", "text": para})
    return out


def _has_word(text: str, w: str) -> bool:
    t = _norm(text).lower()
    w = _norm(w).lower()
    if not w:
        return False
    return bool(re.search(r"(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])", t))


def _word_set(text: str) -> set:
    return {m.group(0).lower() for m in re.finditer(r"[A-Za-z][A-Za-z\-']*|[\u4e00-\u9fff]+", _norm(text))}


# ---------------------------------------------------------------------------
# 逐句切分（逐句对照基础）
# ---------------------------------------------------------------------------
def segment(payload: Dict[str, Any]) -> Dict[str, Any]:
    paras = _paragraphs(payload)
    sentences: List[Dict[str, Any]] = []
    for para in paras:
        pid = str(para.get("id", "P"))
        text = str(para.get("text", "") or "")
        # 按句末标点切（中英文），避开缩写点
        parts = re.split(r"(?<=[.!?。！？])\s+|\n+", text.strip()) if text.strip() else []
        for i, raw in enumerate(parts):
            s = raw.strip()
            if not s:
                continue
            sid = f"{pid}_S{i+1}"
            sentences.append({
                "id": sid, "para_id": pid,
                "section": para.get("section", ""), "kind": para.get("kind", "body"),
                "text": s,
            })
    return {
        "status": STATUS_OK if sentences else STATUS_UNCERTAIN,
        "sentences": sentences,
        "stats": {"paragraph_count": len(paras), "sentence_count": len(sentences)},
    }


# ---------------------------------------------------------------------------
# 守护元素抽取
# ---------------------------------------------------------------------------
def protect(payload: Dict[str, Any]) -> Dict[str, Any]:
    paras = _paragraphs(payload)
    protected: List[Dict[str, Any]] = []
    by_kind: Counter = Counter()
    for para in paras:
        pid = str(para.get("id", "P"))
        text = str(para.get("text", "") or "")
        tokens: List[Dict[str, Any]] = []
        # 优先级：结构化标记（引用/图表/公式/化学式）先于裸数字，
        # 避免 [1] 里的 1 被 NUM_RE 抢走导致 citation 漏抽
        patterns = [
            ("citation", CITE_RE), ("refmark", REFMARK_RE), ("formula", FORMULA_RE),
            ("chemical", CHEM_RE), ("number_unit", UNIT_RE), ("number", NUM_RE),
        ]
        seen_spans: List[Tuple[int, int]] = []
        for kind, pat in patterns:
            for m in pat.finditer(text):
                a, b = m.span()
                if any(not (b <= x or a >= y) for x, y in seen_spans):
                    continue  # 已由更高优先级模式覆盖（如数字单位覆盖裸数字）
                seen_spans.append((a, b))
                tokens.append({"kind": kind, "text": m.group(0), "start": a, "end": b})
                by_kind[kind] += 1
        # 限定词与否定词按词匹配（不去重位置，守恒核验按集合）
        for w in LIMIT_SCALE:
            if _has_word(text, w):
                tokens.append({"kind": "limit", "text": w, "start": -1, "end": -1})
                by_kind["limit"] += 1
        for w in NEG_WORDS:
            if _has_word(text, w):
                tokens.append({"kind": "negation", "text": w, "start": -1, "end": -1})
                by_kind["negation"] += 1
        protected.append({"id": pid, "tokens": tokens})
    return {
        "status": STATUS_OK if protected else STATUS_UNCERTAIN,
        "protected": protected,
        "stats": {"tokens": sum(len(x["tokens"]) for x in protected), "by_kind": dict(by_kind)},
    }


def _token_multiset(protected: Dict[str, Any], kinds: Optional[List[str]] = None) -> Counter:
    c: Counter = Counter()
    for x in protected.get("protected", []):
        for t in x.get("tokens", []):
            if kinds is None or t["kind"] in kinds:
                c[(t["kind"], _norm(t["text"]).lower())] += 1
    return c


# ---------------------------------------------------------------------------
# 改得对：高置信度硬错误检测（保守，不替模型重写）
# ---------------------------------------------------------------------------
def detect_grammar(payload: Dict[str, Any]) -> Dict[str, Any]:
    paras = _paragraphs(payload)
    issues: List[Dict[str, Any]] = []
    for para in paras:
        pid = str(para.get("id", "P"))
        text = str(para.get("text", "") or "")
        # 重复词
        for m in re.finditer(r"\b([A-Za-z]+)\s+\1\b", text, re.I):
            issues.append({"para_id": pid, "type": "repeated_word", "text": m.group(0),
                           "reason": "连续重复词，须删除其一"})
        # 重复标点
        for m in re.finditer(r"([,.;:，。；：])\1+", text):
            issues.append({"para_id": pid, "type": "repeated_punct", "text": m.group(0),
                           "reason": "重复标点，须合并为一个"})
        # 双冠词 / the the
        for m in re.finditer(r"\b(the|a|an)\s+(the|a|an)\b", text, re.I):
            issues.append({"para_id": pid, "type": "double_article", "text": m.group(0),
                           "reason": "连续冠词，须改单"})
        # 句首小写（英文句子）
        for m in re.finditer(r"(?:^|[.!?]\s+)([a-z][a-z\-']*)", text):
            w = m.group(1)
            if w.lower() in ABBREV:
                continue
            issues.append({"para_id": pid, "type": "sentence_start_lowercase", "text": w,
                           "reason": "英文句首应大写"})
        # 中英粘连（数字/英文 与中文之间缺空格，仅提示，不自动改）
        for m in re.finditer(r"[A-Za-z0-9][\u4e00-\u9fff]|[\u4e00-\u9fff][A-Za-z0-9]", text):
            issues.append({"para_id": pid, "type": "cjk_latin_no_space", "text": m.group(0),
                           "reason": "中英/数字与中文相邻，建议按规范加空格（术语/化学式除外）"})
    return {
        "status": STATUS_OK if not issues else STATUS_PARTIAL,
        "issues": issues,
        "stats": {"issue_count": len(issues),
                  "by_type": dict(Counter(i["type"] for i in issues))},
    }


# ---------------------------------------------------------------------------
# 说得像：术语一致性回扫 + 语域诊断
# ---------------------------------------------------------------------------
def check_terms(payload: Dict[str, Any]) -> Dict[str, Any]:
    paras = _paragraphs(payload)
    glossary = [g for g in _get(payload, "glossary", []) or [] if isinstance(g, dict)]
    full_text = "\n".join(str(p.get("text", "") or "") for p in paras)
    inconsistencies: List[Dict[str, Any]] = []
    # 术语表内部冲突：同一 source 多个 target，或同一 target 多个 source（大小写归一）
    by_source: Dict[str, set] = defaultdict(set)
    by_target: Dict[str, set] = defaultdict(set)
    for g in glossary:
        s, t = _norm(g.get("source")), _norm(g.get("target"))
        if s and t:
            by_source[s.lower()].add(t)
            by_target[t.lower()].add(s)
    for s, ts in by_source.items():
        if len(ts) > 1:
            inconsistencies.append({"type": "source_multi_target", "source": s,
                                    "targets": sorted(ts), "reason": "同一术语有多个译法/写法"})
    for t, ss in by_target.items():
        if len(ss) > 1:
            inconsistencies.append({"type": "target_multi_source", "target": t,
                                    "sources": sorted(ss), "reason": "多个术语写成同一形式，可能误合并"})
    # 缩写首现检查：缩写出现但术语表无对应全称
    abbrs = re.findall(r"\b[A-Z]{2,6}\b", full_text)
    locked = {_norm(g.get("source")).lower() for g in glossary}
    missing_abbr = sorted({a for a in abbrs if a.lower() not in locked and a not in STOP})
    return {
        "status": STATUS_OK if not inconsistencies else STATUS_PARTIAL,
        "inconsistencies": inconsistencies,
        "glossary_terms": len(glossary),
        "unlisted_abbreviations": missing_abbr[:20],
        "stats": {"inconsistent_count": len(inconsistencies),
                  "unlisted_abbr_count": len(missing_abbr)},
    }


def check_register(payload: Dict[str, Any]) -> Dict[str, Any]:
    paras = _paragraphs(payload)
    target = _norm(_get(payload, "target_register", "journal")).lower() or "journal"
    full_text = "\n".join(str(p.get("text", "") or "") for p in paras)
    hits: Dict[str, List[str]] = {"colloquial": [], "absolutist": [], "promotional": [], "first_person": []}
    for w in COLLOQUIAL:
        if _has_word(full_text, w):
            hits["colloquial"].append(w)
    for w in ABSOLUTIST:
        if _has_word(full_text, w):
            hits["absolutist"].append(w)
    for w in PROMOTIONAL:
        if _has_word(full_text, w):
            hits["promotional"].append(w)
    for w in FIRST_PERSON:
        if re.search(r"(?:^|\s)" + re.escape(w.strip()) + r"\b", full_text):
            hits["first_person"].append(w.strip())
    # 语气贴合：期刊/摘要更忌口语与宣传；审稿回复允许一定第一人称
    strict = target in ("journal", "abstract")
    notes: List[str] = []
    if strict and hits["colloquial"]:
        notes.append("目标载体=%s，建议消除口语化：%s" % (target, "、".join(hits["colloquial"][:5])))
    if strict and hits["promotional"]:
        notes.append("目标载体=%s，建议淡化宣传化：%s" % (target, "、".join(hits["promotional"][:5])))
    if hits["absolutist"]:
        notes.append("绝对化表述可能削弱结论边界：%s" % "、".join(hits["absolutist"][:5]))
    return {
        "status": STATUS_OK if not any(hits.values()) else STATUS_PARTIAL,
        "target_register": target, "hits": hits,
        "needs_review": notes,
        "stats": {"total": sum(len(v) for v in hits.values())},
    }


# ---------------------------------------------------------------------------
# 没改坏：限定强度守恒 + 守护元素核对（原文 vs 润色文）
# ---------------------------------------------------------------------------
def _polished_map(payload: Dict[str, Any]) -> Dict[str, str]:
    pm = _get(payload, "polished", {}) or {}
    if not isinstance(pm, dict):
        return {}
    return {str(k): str(v) for k, v in pm.items() if isinstance(v, str)}


def check_preserve(payload: Dict[str, Any]) -> Dict[str, Any]:
    paras = _paragraphs(payload)
    pm = _polished_map(payload)
    if not pm:
        return {
            "status": STATUS_UNCERTAIN, "checked": False,
            "needs_review": ["无真实 polished 文本，无法核限定强度守恒（不臆造润色结果）"],
            "issues": [], "stats": {"compared": 0},
        }
    src_prot = protect(payload)
    # 以润色文本构造同结构 payload 做守护抽取
    pol_paras = []
    for p in paras:
        pid = str(p.get("id", "P"))
        if pid in pm:
            q = dict(p); q["text"] = pm[pid]; pol_paras.append(q)
    pol_prot = protect({"paragraphs": pol_paras})
    hard_kinds = ["number_unit", "number", "citation", "refmark", "formula", "chemical"]
    src_hard = _token_multiset(src_prot, hard_kinds)
    pol_hard = _token_multiset(pol_prot, hard_kinds)
    lost = list((src_hard - pol_hard).elements())
    added = list((pol_hard - src_hard).elements())
    # 否定词守恒
    src_neg = _token_multiset(src_prot, ["negation"])
    pol_neg = _token_multiset(pol_prot, ["negation"])
    neg_lost = list((src_neg - pol_neg).elements())
    # 限定强度：原文弱化词须保留；原文无强化词时改文不应新增
    src_lim = _token_multiset(src_prot, ["limit"])
    pol_lim = _token_multiset(pol_prot, ["limit"])
    weakened_lost = [t for (k, t), n in src_lim.items()
                     if LIMIT_SCALE.get(t, 0) == -1 and pol_lim[(k, t)] < n]
    strengthened_added = [t for (k, t), n in pol_lim.items()
                          if LIMIT_SCALE.get(t, 0) == 2 and src_lim[(k, t)] < n]
    issues: List[Dict[str, Any]] = []
    for t in lost:
        issues.append({"type": "protected_lost", "detail": t, "reason": "数字/单位/引用/图表/公式/化学式在润色中丢失或被改"})
    for t in added:
        issues.append({"type": "protected_added", "detail": t, "reason": "润色新增了原文没有的数值/引用/图表指向"})
    for t in neg_lost:
        issues.append({"type": "negation_lost", "detail": t, "reason": "否定词在润色中丢失，可能反转原意"})
    for t in weakened_lost:
        issues.append({"type": "hedge_weakened", "detail": t, "reason": "原文限定/弱化词在润色中丢失，结论边界被加强"})
    for t in strengthened_added:
        issues.append({"type": "claim_strengthened", "detail": t, "reason": "润色新增绝对化词，偷偷加强了结论"})
    return {
        "status": STATUS_UNCERTAIN if issues else STATUS_OK,
        "checked": True,
        "issues": issues,
        "counts": {"protected_lost": len(lost), "protected_added": len(added),
                   "negation_lost": len(neg_lost), "hedge_weakened": len(weakened_lost),
                   "claim_strengthened": len(strengthened_added)},
        "stats": {"compared": len(pol_paras)},
    }


# ---------------------------------------------------------------------------
# 关系核验 + 证据索引
# ---------------------------------------------------------------------------
def verify(payload: Dict[str, Any]) -> Dict[str, Any]:
    gram = detect_grammar(payload)
    terms = check_terms(payload)
    reg = check_register(payload)
    pres = check_preserve(payload)
    needs = list(reg.get("needs_review", [])) + list(pres.get("needs_review", []))
    issues = gram["issues"] + terms["inconsistencies"] + pres["issues"]
    statuses = [gram["status"], terms["status"], reg["status"], pres["status"]]
    overall = STATUS_OK
    if STATUS_UNCERTAIN in statuses:
        overall = STATUS_UNCERTAIN
    elif STATUS_PARTIAL in statuses or issues:
        overall = STATUS_PARTIAL
    return {
        "status": overall, "consistent": not issues,
        "issues": issues, "needs_review": needs,
        "stats": {"issue_count": len(issues), "needs_review_count": len(needs)},
    }


def evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    seg = segment(payload)
    prot = protect(payload)
    prot_map = {x["id"]: [t["kind"] for t in x.get("tokens", [])] for x in prot["protected"]}
    idx = []
    for s in seg["sentences"]:
        idx.append({
            "sentence_id": s["id"], "para_id": s["para_id"],
            "section": s["section"], "text": s["text"],
            "protected_kinds": prot_map.get(s["para_id"], []),
        })
    return {"status": STATUS_OK if idx else STATUS_UNCERTAIN, "evidence": idx,
            "stats": {"count": len(idx)}}


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------
def pipeline(payload: Dict[str, Any], compact: bool = False,
             with_draft: bool = False) -> Dict[str, Any]:
    p = _as_payload(payload)
    seg = segment(p)
    gram = detect_grammar(p)
    terms = check_terms(p)
    reg = check_register(p)
    pres = check_preserve(p)
    prot = protect(p)
    ver = verify(p)
    ev = evidence(p)
    statuses = [seg["status"], gram["status"], terms["status"], reg["status"],
                pres["status"], prot["status"], ver["status"], ev["status"]]
    overall = STATUS_OK
    if STATUS_UNCERTAIN in statuses:
        overall = STATUS_UNCERTAIN
    elif STATUS_PARTIAL in statuses:
        overall = STATUS_PARTIAL
    has_polished = bool(_polished_map(p))
    draft_obj = render_draft(p) if with_draft else None
    result = {
        "paragraph_count": seg["stats"]["paragraph_count"],
        "sentence_count": seg["stats"]["sentence_count"],
        "grammar_issues": gram["stats"]["issue_count"],
        "term_inconsistencies": terms["stats"]["inconsistent_count"],
        "register_flags": reg["stats"]["total"],
        "protected_tokens": prot["stats"]["tokens"],
        "preservation": {"checked": pres.get("checked", False), "counts": pres.get("counts", {}),
                         "issue_count": len(pres.get("issues", []))},
        "verification": {"consistent": ver["consistent"], "issues": ver["issues"],
                         "needs_review": ver["needs_review"]},
        "evidence_index": ev["evidence"],
        "summary": (
            "段 %d / 句 %d；硬错误 %d；术语不一致 %d；语域提示 %d；"
            "守护元素 %d（数值/引用/图表/公式/化学式/限定/否定）；"
            "守恒核验 %s（问题 %d）；核验问题 %d（待确认 %d）" % (
                seg["stats"]["paragraph_count"], seg["stats"]["sentence_count"],
                gram["stats"]["issue_count"], terms["stats"]["inconsistent_count"],
                reg["stats"]["total"], prot["stats"]["tokens"],
                "已做" if pres.get("checked") else "未做(无真实润色文)",
                len(pres.get("issues", [])), ver["stats"]["issue_count"],
                ver["stats"]["needs_review_count"])),
    }
    out = {"case_id": _get(p, "case_id"), "status": overall, "has_polished": has_polished}
    if not compact:
        out["pipeline"] = {"segment": seg, "grammar": gram, "terms": terms,
                           "register": reg, "preserve": pres, "protect": prot,
                           "verify": ver, "evidence": ev}
    if draft_obj:
        result["polished_draft"] = draft_obj.get("polished_text", "")
        result["draft_detail"] = draft_obj
    out["result"] = result
    return out


# ---------------------------------------------------------------------------
# 完成器：真实输入适配 / 润色成稿 / result.json 装配 / 端到端 solve
# ---------------------------------------------------------------------------
def _adapt_case(payload: Dict[str, Any], case_dir: str) -> Dict[str, Any]:
    """真实输入适配器：把 source_files / source_text 读成段落；合并术语表与真实润色文。

    支持：
      - paragraphs（内联结构化）
      - source_text（单篇纯文本，按空行/换行切段）
      - source_files（[路径] 或 {名:路径}，读 .txt/.md/.json）
      - glossary_file（术语表文件：.json 列表 或 TSV 两列）
      - polished_files / polished（{段号:路径} 或 {段号:文本}，真实润色文本，不臆造）
    读不到不臆造，记入 adapter_notes 交给缺口清单。
    """
    import os as _os
    work = dict(payload)
    notes: List[str] = []

    paras = list(_paragraphs(work))
    if not paras and _get(work, "source_text"):
        raw = str(_get(work, "source_text"))
        chunks = [c.strip() for c in re.split(r"\n\s*\n|\n", raw) if c.strip()]
        paras = [{"id": f"P{i+1}", "section": "", "kind": "body", "text": c}
                 for i, c in enumerate(chunks)]
        notes.append("source_text 切段 %d" % len(paras))

    files = work.get("source_files") or []
    if isinstance(files, dict):
        files = list(files.values())
    for rel in files:
        path = str(rel) if _os.path.isabs(str(rel)) else _os.path.join(case_dir, str(rel))
        try:
            raw = open(path, encoding="utf-8").read()
        except Exception:
            notes.append("读取失败:%s" % _os.path.basename(path))
            continue
        if path.lower().endswith(".json"):
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and isinstance(data.get("paragraphs"), list):
                    paras.extend(data["paragraphs"])
                    notes.append("json段:%s=%d" % (_os.path.basename(path), len(data["paragraphs"])))
                    continue
            except Exception:
                pass
        chunks = [c.strip() for c in re.split(r"\n\s*\n|\n", raw) if c.strip()]
        name = _os.path.splitext(_os.path.basename(path))[0]
        paras.extend({"id": f"{name}_P{i+1}", "section": name, "kind": "body", "text": c}
                     for i, c in enumerate(chunks))
        notes.append("文本:%s=%d段" % (_os.path.basename(path), len(chunks)))
    work["paragraphs"] = paras

    # 术语表文件
    gf = _get(work, "glossary_file", "")
    if gf:
        path = str(gf) if _os.path.isabs(str(gf)) else _os.path.join(case_dir, str(gf))
        try:
            raw = open(path, encoding="utf-8").read()
            gl = list(work.get("glossary") or [])
            if str(gf).lower().endswith(".json"):
                data = json.loads(raw)
                gl += data.get("glossary", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            else:
                for line in raw.splitlines():
                    cols = re.split(r"\t|,", line.strip())
                    if len(cols) >= 2 and cols[0] and not cols[0].startswith("#"):
                        gl.append({"source": cols[0].strip(), "target": cols[1].strip()})
            work["glossary"] = gl
            notes.append("术语表:%s" % _os.path.basename(path))
        except Exception:
            notes.append("术语表读取失败:%s" % _os.path.basename(path))

    # 真实润色文本（可选）
    polished = dict(work.get("polished") or {})
    pf = work.get("polished_files") or {}
    if isinstance(pf, dict):
        for pid, val in pf.items():
            if polished.get(pid):
                continue
            v = str(val)
            if _os.path.isabs(v) or _os.sep in v:
                path = v if _os.path.isabs(v) else _os.path.join(case_dir, v)
                try:
                    polished[pid] = open(path, encoding="utf-8").read()
                except Exception:
                    notes.append("润色文读取失败:%s" % pid)
            else:
                polished[pid] = v  # 内联真实文本，不臆造
    if polished:
        work["polished"] = polished
    work["adapter_notes"] = notes
    return work


def render_draft(payload: Dict[str, Any]) -> Dict[str, Any]:
    """用真实字段渲染【可编辑、可逐句回溯的润色成稿草稿】——完成器核心。

    硬约束：
      - 只用真实段落原文、真实 polished 改文、真实 glossary 术语；
      - 无真实改文的句标〔待润色〕，绝不臆造润色措辞；
      - 每句给 原文—改文—修改类型—理由—守护依据—核验结论；
      - 术语漂移、语域问题、否定/限定丢失、绝对化新增 → 待确认清单，不写成既成事实。
    """
    p = _as_payload(payload)
    seg = segment(p)
    gram = detect_grammar(p)
    terms = check_terms(p)
    reg = check_register(p)
    pres = check_preserve(p)
    prot = protect(p)
    pm = _polished_map(p)
    prot_map = {x["id"]: [t["kind"] for t in x.get("tokens", [])] for x in prot["protected"]}
    glossary = [g for g in _get(p, "glossary", []) or [] if isinstance(g, dict)]
    # 段落级硬错误归属
    gram_by_para: Dict[str, List[str]] = defaultdict(list)
    for i in gram["issues"]:
        gram_by_para[str(i.get("para_id", ""))].append(i.get("type", ""))
    # 守护问题归属（守恒问题多为段落级，统一列证据）
    pres_issues = pres.get("issues", [])
    confirm: List[str] = []
    for c in terms["inconsistencies"]:
        confirm.append("术语一致性：%s" % c.get("reason", c.get("type", "")))
    confirm += reg.get("needs_review", [])
    for i in pres_issues:
        confirm.append("%s：%s" % (i.get("type", ""), i.get("reason", "")))
    confirm += pres.get("needs_review", [])

    blocks: List[Dict[str, Any]] = []
    pending: List[str] = []
    for s in seg["sentences"]:
        sid, pid = s["id"], s["para_id"]
        src = s.get("text", "")
        polished = pm.get(pid, "")
        # 句级改文：仅当该段有真实 polished 且能定位到本句时给出，否则标待润色
        polished_sent = ""
        if polished:
            cand = [c.strip() for c in re.split(r"(?<=[.!?。！？])\s+|\n+", polished) if c.strip()]
            idx = 0
            m = re.match(r".*_S(\d+)$", sid)
            if m:
                idx = int(m.group(1)) - 1
            polished_sent = cand[idx] if idx < len(cand) else ""
        if polished_sent and polished_sent != src:
            target, status = polished_sent, "polished"
        elif polished_sent == src and src:
            target, status = src, "unchanged"
        else:
            target = "〔待润色：须由模型在术语锁定+限定强度守恒+守护元素约束下补全，脚本不臆造措辞〕"
            status = "needs_polish"
            pending.append(sid)
        types = gram_by_para.get(pid, [])
        used_terms = [{"source": _get(g, "source"), "target": _get(g, "target")}
                      for g in glossary if _get(g, "source") and _has_word(src, str(_get(g, "source")))]
        blocks.append({
            "id": sid, "para_id": pid, "section": s.get("section", ""), "kind": s.get("kind", "body"),
            "source": src, "target": target,
            "change_types": sorted(set(types)),
            "reasons": ["确定性检测到：%s" % t for t in sorted(set(types))],
            "glossary_basis": used_terms,
            "protected_kinds": prot_map.get(pid, []),
            "status": status,
        })

    polished_text = "\n\n".join(
        "[%s] 原文: %s\n      改文: %s" % (b["id"], b["source"], b["target"]) for b in blocks)
    all_ok = bool(blocks) and not pending and not confirm and not gram["issues"]
    return {
        "case_id": _get(p, "case_id", ""),
        "status": "draft" if all_ok else "partial",
        "polished_text": polished_text,
        "polished_draft": polished_text,
        "blocks": blocks,
        "source_refs": [b["id"] for b in blocks],
        "pending_polish": pending,
        "needs_author_confirmation": confirm,
        "term_inconsistencies": terms["inconsistencies"],
        "register_flags": reg["hits"],
        "preservation_issues": pres_issues,
        "unverified_relations": [i for i in pres_issues
                                 if i.get("type") in ("protected_lost", "negation_lost",
                                                      "hedge_weakened", "claim_strengthened")],
        "uncertainty": [
            "只用真实段落/润色文/术语成稿；无改文标〔待润色〕，不臆造润色措辞或术语写法",
            "限定强度、因果边界、语域是否贴合属价值判断，须结合原意人工复核",
            "硬错误检测为高置信度保守模式，未标句子不等于无误，须通读复核",
        ],
        "note": ("可编辑逐句润色成稿草稿：句号+定位+原文+改文/待润色+修改类型与理由+"
                 "术语与守护依据+核验结论；非最终译文，待润色句须由模型在锁定约束下补全再核验。"),
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
    """端到端完成器：读 case.json → 适配真实材料 → 全流程 → 润色成稿 → 装配 result.json。"""
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
    cid = str(_get(payload, "case_id", "") or "")
    work = _adapt_case(payload, case_dir)
    if not _paragraphs(work):
        result = {"case_id": cid, "status": STATUS_UNCERTAIN, "input_mode": "case",
                  "result": {"summary": "输入无 paragraphs/source_text/source_files，无法成稿（不臆造润色）"},
                  "needs_review": ["请提供真实稿件段落或材料文件"]}
        result["delivery"] = _write_solution(result, out_dir, cid)
        return result

    pl = pipeline(work, with_draft=True)
    r = pl["result"]
    draft = r.get("draft_detail") or {}
    result = {
        "case_id": cid,
        "status": pl["status"],
        "input_mode": "case",
        "source_count": len(_paragraphs(work)),
        "adapter_notes": work.get("adapter_notes", []),
        "result": {
            "polished_draft": r.get("polished_draft", draft.get("polished_text", "")),
            "draft_text": r.get("polished_draft", draft.get("polished_text", "")),
            "blocks": draft.get("blocks", []),
            "paragraph_count": r["paragraph_count"],
            "sentence_count": r["sentence_count"],
            "grammar_issues": r["grammar_issues"],
            "term_inconsistencies": r["term_inconsistencies"],
            "register_flags": r["register_flags"],
            "protected_tokens": r["protected_tokens"],
            "preservation": r["preservation"],
            "verification": r["verification"],
            "evidence_index": r["evidence_index"],
            "summary": r["summary"],
            "status_checks": pl["status"],
        },
        "needs_review": draft.get("needs_author_confirmation", []) + r["verification"].get("needs_review", []),
        "uncertainty": draft.get("uncertainty", []),
    }
    result["delivery"] = _write_solution(result, out_dir, cid)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load(path: str):
    if path == "-":
        import sys as _s
        return json.load(_s.stdin)
    return json.load(open(path, "r", encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="学术语言润色守门/完成引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("segment", "protect", "detect_grammar", "check_terms", "check_register",
              "check_preserve", "verify", "evidence", "pipeline", "render-draft"):
        sp = sub.add_parser(c); sp.add_argument("input")
        if c == "pipeline":
            sp.add_argument("--compact", action="store_true")
            sp.add_argument("--with-draft", action="store_true")
    sv = sub.add_parser("solve", help="端到端完成器：case.json →(适配材料)→ 全流程 → 润色成稿 → result.json")
    sv.add_argument("case", help="case.json 路径")
    sv.add_argument("--out", default="/app/output", help="交付目录")
    args = ap.parse_args(argv)
    if args.cmd == "solve":
        out = solve(args.case, args.out)
        sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
        return 0
    data = _load(args.input)
    p = _as_payload(data)
    cmds = {
        "segment": segment, "protect": protect, "detect_grammar": detect_grammar,
        "check_terms": check_terms, "check_register": check_register,
        "check_preserve": check_preserve, "verify": verify, "evidence": evidence,
        "render-draft": render_draft,
    }
    if args.cmd in cmds:
        out = cmds[args.cmd](p)
    elif args.cmd == "pipeline":
        out = pipeline(p, compact=args.compact, with_draft=args.with_draft)
    else:
        ap.error("未知命令"); return 2
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
