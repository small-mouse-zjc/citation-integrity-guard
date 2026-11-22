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
from collections import Counter
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
    # 空输入门禁：没有可识别章节时不得判为“对齐”，否则空笔记会经 pipeline 报 ok
    empty_input = not paper_keys or not note_keys

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
        "empty_input": empty_input,
        "aligned": (not empty_input) and order_ok and not missing,
        "advice": ("输入为空：论文或笔记缺少可识别章节，无法判定对齐，须先补齐章节"
                   if empty_input else
                   ("笔记骨架与论文章节对齐" if order_ok and not missing
                    else f"笔记漏章节 {missing} 或顺序不一致（倒序 {inversions[:3]}），须按论文自身结构重排")),
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
    # 空输入门禁：整张卡片没有任何实质内容时不得判为“字段齐全”
    empty_input = not any(str(card.get(k, "") or "").strip() for k in required) and not str(card.get("note", "") or "").strip()
    return {
        "fields": report,
        "present_count": n,
        "required_count": len(required),
        "empty_input": empty_input,
        "missing": missing,
        "complete": (not empty_input) and not missing,
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
    # 空输入门禁：没有任何笔记时不得判为“全部可回链”
    empty_input = len(results) == 0
    return {
        "notes": results,
        "note_count": len(results),
        "anchored_count": anchored,
        "no_anchor": no_anchor,
        "bad_anchor": bad_anchor,
        "empty_input": empty_input,
        "all_anchored": (not empty_input) and not no_anchor and not bad_anchor,
        "advice": ("输入为空：没有任何关键笔记，无法判定锚点可回链，须先产出笔记"
                   if empty_input else
                   ("每条笔记均可回链原文" if not no_anchor and not bad_anchor
                    else f"{len(no_anchor)} 条缺锚点、{len(bad_anchor)} 条锚点无效，须补具体定位")),
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
STOPWORDS = {"the", "a", "an", "of", "and", "to", "in", "is", "are", "for", "with",
             "on", "that", "this", "we", "our", "study", "paper", "method",
             "result", "results", "using", "based", "can", "be", "by"}


def _point_text(p: Dict[str, Any]) -> str:
    for k in ("statement", "point", "text", "content", "title", "claim", "label"):
        if p.get(k):
            return str(p[k])
    return ""


def synthesize_themes(points: List[Dict[str, Any]], threshold: float = 0.45,
                      min_shared: int = 2) -> Dict[str, Any]:
    """把知识点聚成主题簇：同簇内共享实词，输出主题标签与覆盖度。

    去重只解决“重复”，聚类才回答“这些发现能否拼成几条主线”。
    """
    items = []
    for i, p in enumerate(points or []):
        txt = _point_text(p)
        toks = {w for w in _norm(txt).split() if w and w not in STOPWORDS and len(w) > 1}
        # 中文无空格：用二字切片补足可比较的实词单元，否则中文知识点永远无法聚类
        for seg in re.findall(r"[\u4e00-\u9fff]{2,}", txt):
            for k in range(len(seg) - 1):
                toks.add(seg[k:k + 2])
        items.append({"id": str(p.get("id") or ("kp%d" % (i + 1))), "text": txt, "tokens": toks})
    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i]["tokens"], items[j]["tokens"]
            if not a or not b:
                continue
            shared = a & b
            ov = len(shared) / min(len(a), len(b))
            # 中文二字切片会摊薄 Jaccard；共享 3 个实词单元，或共享 2 个且占短文本 45% 即同主题
            if len(shared) >= 3 or (len(shared) >= 2 and ov >= threshold):
                union(i, j)
    clusters: Dict[int, List[int]] = {}
    for i in range(len(items)):
        clusters.setdefault(find(i), []).append(i)
    out_clusters = []
    for idxs in clusters.values():
        common: Counter = Counter()
        for i in idxs:
            common.update(items[i]["tokens"])
        keywords = [w for w, _ in common.most_common(5)]
        out_clusters.append({
            "theme_id": "T%d" % (len(out_clusters) + 1),
            "label": items[idxs[0]]["text"][:40] or "未命名主题",
            "point_ids": [items[i]["id"] for i in idxs],
            "size": len(idxs),
            "keywords": keywords,
        })
    out_clusters.sort(key=lambda c: (-c["size"], c["theme_id"]))
    for k, c in enumerate(out_clusters, 1):
        c["theme_id"] = "T%d" % k
    singletons = [c["point_ids"][0] for c in out_clusters if c["size"] == 1]
    covered = sum(c["size"] for c in out_clusters if c["size"] > 1)
    return {
        "point_count": len(items), "cluster_count": len(out_clusters),
        "clusters": out_clusters, "singletons": singletons,
        "coverage": round(covered / len(items), 3) if items else 0.0,
        "advice": ("知识点已成 %d 条主题线（覆盖 %d/%d）" % (len(out_clusters), covered, len(items))
                   if items else "无知识点，无法聚类"),
    }


def pipeline(payload: Dict[str, Any], with_draft: bool = False) -> Dict[str, Any]:
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
    r_themes = synthesize_themes(r_know.get("entries") or points)
    r_readcard = build_reading_card(card)

    # 全局空输入门禁：三段核心输入任一为空，都不得报 ok
    any_empty = (r_align.get("empty_input") or r_card.get("empty_input") or
                 r_anchor.get("empty_input"))
    overall = (not any_empty and r_align["aligned"] and r_card["complete"] and
               r_anchor["all_anchored"] and not r_know["needs_review"])
    draft_obj = render_draft(payload) if with_draft else None
    return {
        "case_id": case_id,
        "status": "ok" if overall else "needs_attention",
        "result": {
            "section_alignment": r_align,
            "card_fields": r_card,
            "anchor_verification": r_anchor,
            "knowledge_normalization": r_know,
            "theme_synthesis": r_themes,
            "reading_card": r_readcard,
            "structured_notes": payload.get("notes", []),
        },
        "draft_detail": draft_obj,
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
            "empty_inputs": {
                "sections": bool(r_align.get("empty_input")),
                "card": bool(r_card.get("empty_input")),
                "notes": bool(r_anchor.get("empty_input")),
            },
            "note": ("笔记是否忠实原文、锚点是否真对应属价值判断，须 Agent 结合原文复核；"
                     "脚本只做结构与格式校验，不臆造未报告内容"),
        },
    }


# ---------------------------------------------------------------------------
# 完成器：真实输入适配 / 结构化笔记成稿 / result.json 装配 / 端到端 solve
# ---------------------------------------------------------------------------
def _adapt_case(payload: Dict[str, Any], case_dir: str) -> Dict[str, Any]:
    """真实输入适配器：把真实论文材料读成章节文本 + 笔记 + 卡片字段。

    支持：
      - paper_sections / note_sections / card / notes（内联，已结构化）
      - paper_text（真实论文全文，按章节标题行切段为 paper_sections）
      - section_files（[路径] 或 {章节名:路径}）——读真实 .txt/.md/.json
      - notes_text（真实笔记全文，按行/条目切为 notes）
      - notes_files（{锚点:路径}）——读真实笔记片段
    读不到不臆造，记录到 adapter_notes。
    """
    import os as _os
    work = dict(payload)
    notes_log: List[str] = []

    sections = list(work.get("paper_sections") or [])
    if not sections and _get_str(work, "paper_text"):
        raw = str(work["paper_text"])
        # 按「摘要/引言/方法/结果/讨论/结论」等章节标题行切段
        heads = SECTION_ORDER
        sections = [s.strip() for s in re.split(r"\n\s*\n|\n", raw) if s.strip()]
        # 保留原文行作为章节标签（若命中已知章节，规范为标题词）
        sections = [_canon_section(s) for s in sections]
        notes_log.append("paper_text 切段 %d" % len(sections))
    files = work.get("section_files") or []
    if isinstance(files, dict):
        files = [{k: v} for k, v in files.items()]
    # 字符串路径项归一化为 {文件名: 路径}
    files = [{_os.path.basename(str(x)): x} if isinstance(x, str) else x for x in files]
    for ent in files:
        if isinstance(ent, dict):
            for name, rel in ent.items():
                path = str(rel) if _os.path.isabs(str(rel)) else _os.path.join(case_dir, str(rel))
                try:
                    raw = open(path, encoding="utf-8").read()
                except Exception:
                    notes_log.append("读取失败:%s" % _os.path.basename(path))
                    continue
                if path.lower().endswith(".json"):
                    try:
                        data = json.loads(raw)
                        if isinstance(data, dict):
                            for key in ("paper_sections", "sections"):
                                if isinstance(data.get(key), list):
                                    sections.extend(data[key])
                            for key in ("card", "fields"):
                                if isinstance(data.get(key), dict):
                                    work.setdefault("card", {}).update(data[key])
                            notes_log.append("json材料:%s" % _os.path.basename(path))
                            continue
                    except Exception:
                        pass
                chunks = [c.strip() for c in re.split(r"\n\s*\n|\n", raw) if c.strip()]
                sections.extend(chunks)
                notes_log.append("文本文件:%s=%d段" % (_os.path.basename(path), len(chunks)))
    work["paper_sections"] = sections

    notes = list(work.get("notes") or [])
    if not notes and _get_str(work, "notes_text"):
        lines = [ln.strip() for ln in str(work["notes_text"]).splitlines() if ln.strip()]
        notes = [{"id": "n%d" % (i + 1), "text": ln} for i, ln in enumerate(lines)]
        notes_log.append("notes_text 切条 %d" % len(notes))
    nfiles = work.get("notes_files") or {}
    if isinstance(nfiles, dict):
        for anchor, rel in nfiles.items():
            path = str(rel) if _os.path.isabs(str(rel)) else _os.path.join(case_dir, str(rel))
            try:
                txt = open(path, encoding="utf-8").read()
                notes.append({"id": "n%d" % (len(notes) + 1), "text": txt, "anchor": anchor})
                notes_log.append("笔记文件:%s" % anchor)
            except Exception:
                notes_log.append("笔记读取失败:%s" % anchor)
    if notes:
        work["notes"] = notes

    # valid_anchors：内联优先，否则从笔记自带 anchor 汇总
    if not work.get("valid_anchors") and notes:
        work["valid_anchors"] = [n["anchor"] for n in notes if n.get("anchor")]
    work["adapter_notes"] = notes_log
    return work


def _get_str(p: Dict[str, Any], key: str) -> str:
    v = p.get(key)
    return v if isinstance(v, str) else ""


def _canon_section(line: str) -> str:
    """把原文行规范为章节标题词（命中已知章节时），否则保留原行前 40 字。"""
    for key in SECTION_ORDER:
        pats = SECTION_HINTS[key]
        if _has(line[:30], pats):
            return key
    return line[:40]


def render_draft(payload: Dict[str, Any]) -> Dict[str, Any]:
    """用真实字段渲染【可编辑、可回链的逐章结构化笔记成稿】——完成器核心。

    硬约束：
      - 章节骨架只取真实 paper_sections；笔记只取真实 notes；
      - 六字段卡片只用真实 card 字段，缺的标〔待补：未报告〕，不臆造；
      - 每条笔记带锚点，悬空锚点标记待确认；
      - 知识点去重归一，同义但不敢自动合并的进待确认。
    """
    p = payload
    sections = list(p.get("paper_sections") or [])
    notes = list(p.get("notes") or [])
    card = dict(p.get("card") or {})
    points = list(p.get("knowledge_points") or [])
    valid_anchors = p.get("valid_anchors")

    r_align = check_section_alignment(sections, [s for s in sections])
    r_card = build_reading_card(card)
    r_anchor = verify_anchors(notes, valid_anchors)
    r_know = normalize_knowledge(points, p.get("dup_threshold", 0.72))

    # 逐章笔记：章节 → 命中该章的笔记（按 anchor 或文本包含）
    chapter_blocks = []
    for sec in sections:
        sec_norm = _norm(sec)
        related = [n for n in notes
                   if sec_norm and (sec_norm in _norm(n.get("text", "")) or
                                    sec_norm in _norm(n.get("anchor", "")))]
        chapter_blocks.append({
            "section": sec,
            "notes": [{"id": n.get("id", ""), "text": n.get("text", ""),
                       "anchor": n.get("anchor", "〔待补：无锚点〕")} for n in related],
            "status": "ok" if related else "needs_content",
        })
    # 未被任何章节吸收的笔记单列
    absorbed = {n.get("id") for b in chapter_blocks for n in b["notes"]}
    orphans = [{"id": n.get("id", ""), "text": n.get("text", ""),
                "anchor": n.get("anchor", "〔待补：无锚点〕")}
               for n in notes if n.get("id") not in absorbed]

    card_lines = []
    for key, meta in CARD_FIELDS.items():
        entry = r_card["card"][key]
        val = entry.get("value")
        line = "- %s：%s" % (meta["label"], val if val else "〔待补：原文未报告〕")
        if entry.get("anchor"):
            line += "（锚点：%s）" % entry["anchor"]
        card_lines.append(line)
    card_text = "\n".join(card_lines)

    point_lines = ["- %s：%s%s" % (
        e.get("label", ""), e.get("definition", ""),
        "（锚点：%s）" % e["anchor"] if e.get("anchor") else "")
        for e in r_know.get("entries", [])]
    point_text = "\n".join(point_lines) if point_lines else "〔待补：无可归一知识点〕"

    full_text = "\n\n".join(
        ["# 逐章笔记"] +
        ["## %s\n%s" % (b["section"], "\n".join("  - [%s] %s（%s）" % (
            n["id"], n["text"], n["anchor"]) for n in b["notes"]) or "〔待补：本章无笔记〕")
         for b in chapter_blocks] +
        (["## 游离笔记"] + ["  - [%s] %s（%s）" % (n["id"], n["text"], n["anchor"])
                          for n in orphans] if orphans else []) +
        ["# 论文卡片\n" + card_text, "# 知识点\n" + point_text])

    confirm = ["卡片字段『%s』未报告" % f for f in r_card["missing_fields"]]
    confirm += ["笔记 %s 锚点悬空/无效" % n["id"] for n in
                (r_anchor.get("no_anchor", []) + r_anchor.get("bad_anchor", []))]
    confirm += ["知识点『%s』近似但须人工确认是否合并" % m.get("reason", "")
                for m in r_know.get("needs_review", [])]

    all_ok = (bool(sections) and bool(notes) and not confirm and
              not any(b["status"] == "needs_content" for b in chapter_blocks))
    return {
        "case_id": p.get("case_id", ""),
        "status": "draft" if all_ok else "partial",
        "draft_text": full_text,
        "chapter_blocks": chapter_blocks,
        "orphan_notes": orphans,
        "reading_card": r_card["card"],
        "knowledge_entries": r_know.get("entries", []),
        "source_refs": sorted(set(n.get("anchor", "") for n in notes if n.get("anchor"))),
        "needs_author_confirmation": confirm,
        "uncertainty": [
            "章节骨架、笔记、卡片字段只取真实输入；缺的标〔待补〕，不臆造内容或锚点",
            "笔记是否忠实原文、锚点是否真对应、知识点是否同义属价值判断，须人工复核",
        ],
        "note": ("可编辑结构化笔记成稿：逐章笔记 + 六字段卡片 + 知识点 + 锚点回链；"
                 "非最终稿，缺口以〔待补〕标注，须结合原文补全与复核。"),
    }


def _write_solution_core(result: Dict[str, Any], out_dir: str, case_id: str) -> Dict[str, Any]:
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
    """端到端完成器：读 case.json → 适配真实材料 → 校验 → 笔记成稿 → 装配 result.json。"""
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
    if not work.get("paper_sections") and not work.get("notes"):
        result = {"case_id": cid, "status": "needs_attention", "input_mode": "case",
                  "result": {"summary": "输入无章节/笔记/材料文件，无法成稿（不伪造内容）"},
                  "needs_review": ["请提供真实论文材料（paper_sections/paper_text/section_files）"]}
        result["delivery"] = _write_solution(result, out_dir, cid)
        return result

    pl = pipeline(work, with_draft=True)
    draft = pl.get("draft_detail") or {}
    result = {
        "case_id": cid,
        "status": pl["status"],
        "input_mode": "case",
        "source_count": len(work.get("paper_sections", [])),
        "adapter_notes": work.get("adapter_notes", []),
        "result": {
            "draft_text": draft.get("draft_text", ""),
            "chapter_blocks": draft.get("chapter_blocks", []),
            "reading_card": draft.get("reading_card", {}),
            "knowledge_entries": draft.get("knowledge_entries", []),
            "section_alignment": pl["result"]["section_alignment"],
            "card_fields": pl["result"]["card_fields"],
            "anchor_verification": pl["result"]["anchor_verification"],
            "structured_notes": pl["result"]["structured_notes"],
            "summary": ("逐章笔记 %d 章；卡片 %d/6 字段；锚点回链 %d/%d；知识点 %d 条" % (
                len(draft.get("chapter_blocks", [])),
                6 - len(pl["result"]["card_fields"]["missing"]),
                pl["result"]["anchor_verification"]["anchored_count"],
                len(work.get("notes", [])),
                len(draft.get("knowledge_entries", [])))),
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

    sub.add_parser("render-draft", help="用真实字段渲染逐章结构化笔记成稿草稿").add_argument("input", help="JSON 全量输入")
    sv = sub.add_parser("solve", help="端到端完成器：case.json →(适配材料)→ 成稿 → result.json")
    sv.add_argument("case", help="case.json 路径")
    sv.add_argument("--out", default="/app/output", help="交付目录")
    pl = sub.add_parser("pipeline", help="端到端（--with-draft 出成稿）")
    pl.add_argument("input", help="JSON 全量输入")
    pl.add_argument("--with-draft", action="store_true", help="脚本渲染成稿草稿")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help(); return 0

    if args.cmd == "solve":
        out = solve(args.case, args.out)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

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
    elif args.cmd == "render-draft":
        out = render_draft(_load(args.input))
    elif args.cmd == "pipeline":
        out = pipeline(_load(args.input), with_draft=args.with_draft)
    else:
        p.print_help(); return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0

def _write_solution(result, out_dir, case_id):
    """写 result.json，并把 result 渲染成可读、可编辑的交付物（artifacts.py）。"""
    core = _write_solution_core(result, out_dir, case_id)
    try:
        from artifacts import write_artifacts
        core["artifacts"] = write_artifacts(result, out_dir, "paper-note-archivist")
    except Exception as e:  # 渲染失败不影响 result.json 已落盘
        core["artifacts_error"] = type(e).__name__
    return core

if __name__ == "__main__":
    sys.exit(main())
