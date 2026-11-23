#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kg_engine.py — 文献知识图谱构建确定性引擎（纯 Python 3 标准库）

围绕题面四个核心问题：
  抽得准 extract-entities : 实体是否真在论文出现、类型合法、保留位置与原文、区分自述/转述
  连得对 check-relations  : 关系类型/方向/条件是否与原文一致，不把共现或推测当直接证据
  对得齐 align-entities   : 别名/缩写/大小写/同名冲突正确处理，跨篇同表面不得强行合并
  查得到 query-graph      : 至少 3 个真实查询，结果子图可回到论文段落与原文片段
另含：
  bind-source             : 逐节点/边核验来源绑定（source_id + JATS 段落 ID + 原文短引）
  incremental-update      : 增量加入新论文，保留既有节点编号，记录新增/合并/冲突
  check-export            : 图谱导出可读且字段齐全、可序列化

不臆造实体、关系、证据或来源；脚本只做结构与规则校验，价值判断留给 Agent 结合原文复核。
"""
import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 受控词表与正则
# ---------------------------------------------------------------------------
ENTITY_TYPES = {
    "researcher", "material", "method", "task", "metric", "conclusion",
    "dataset", "model", "phenomenon",   # 允许合理扩展的科研对象类型
}
ENTITY_TYPE_ZH = {
    "researcher": "研究者", "material": "材料", "method": "方法", "task": "任务",
    "metric": "指标", "conclusion": "结论", "dataset": "数据集", "model": "模型",
    "phenomenon": "现象",
}

# 关系类型 -> 中文；方向性由 relation 自带 subject/object 决定
RELATION_TYPES = {
    "uses", "applies", "proposes", "compares", "outperforms", "measures",
    "supports", "contradicts", "reports", "derives-from", "evaluated-on",
    "achieves", "correlates-with",
}

# 弱证据类型：不能当成"直接关系"的证据（共现/综述转述/推测/推理）
WEAK_EVIDENCE = {"cooccurrence", "hearsay", "speculation", "inference", "common-knowledge"}
DIRECT_EVIDENCE = {"direct", "quoted", "table", "figure"}

# JATS 段落 ID：形如 p1 / sec2.p3 / sec3.1.p5 / abs1 / tbl2 / fig4 / fn1 等
JATS_ID_RE = re.compile(r"^(abs|abstract|title|p|sec|fn|tbl|tab|fig|app|suppl)[\w.\-]*$", re.I)
# 伪页码：把自建“第1页/page 1/页1”当原文位置，题面明确禁止
FAKE_PAGE_RE = re.compile(r"^(page|p\.?|第)\s*\d+\s*(页)?$|^pdf\s*页", re.I)

AUTHOR_SELF = {"self", "author", "authors", "自述", "作者", "本文", "我们"}
OTHER_REPORT = {"other", "cited", "review", "转述", "他人", "综述", "引用", "文献"}


def _norm(s: str) -> str:
    """归一：小写、压缩空白、去首尾标点。用于表面形式比对，不用于合并判断。"""
    if not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r"[\s\u3000]+", "", s)
    s = re.sub(r"^[，。；、,.;:：]+|[，。；、,.;:：]+$", "", s)
    return s


def _norm_loose(s: str) -> str:
    """更宽松：去连字符、下划线、括号，用于别名/缩写候选比对。"""
    return re.sub(r"[\-_\(\)（）]", "", _norm(s))


def _in_source(source_index: Dict[str, Dict[str, str]], source_id: str,
               paragraph_id: str, needle: str) -> bool:
    """在给定论文的给定 JATS 段落原文里查找字符串。"""
    paras = source_index.get(source_id)
    if not isinstance(paras, dict):
        return False
    text = paras.get(paragraph_id, "")
    if not isinstance(text, str) or not text:
        return False
    if not needle:
        return False
    return _norm(needle) in _norm(text) or needle in text


# ---------------------------------------------------------------------------
# 抽得准：实体
# ---------------------------------------------------------------------------
def check_entity(entity: Dict[str, Any],
                 source_index: Optional[Dict[str, Dict[str, str]]] = None,
                 known_papers: Optional[List[str]] = None) -> Dict[str, Any]:
    """核验单个实体：类型合法、表面形式出现在原文、位置为 JATS ID、原文短引可回查、表述身份清楚。"""
    issues: List[Dict[str, Any]] = []
    surface = entity.get("surface", "") or entity.get("label", "")
    etype = entity.get("type", "")
    source_id = entity.get("source_id", "")
    paragraph_id = entity.get("paragraph_id", "")
    quote = entity.get("quote", "") or entity.get("evidence", "")
    attribution = entity.get("attribution", "self")

    if etype not in ENTITY_TYPES:
        issues.append({"type": "bad_entity_type", "detail": "实体类型不在受控词表: %s" % etype})
    if not surface:
        issues.append({"type": "empty_surface", "detail": "实体表面形式为空"})
    if not source_id:
        issues.append({"type": "no_source_id", "detail": "缺论文来源标识"})
    elif known_papers is not None and source_id not in known_papers:
        issues.append({"type": "unknown_source_id", "detail": "source_id 不在论文集合: %s" % source_id})

    jats_ok = bool(JATS_ID_RE.match(paragraph_id or ""))
    if not paragraph_id:
        issues.append({"type": "no_anchor", "detail": "缺原文段落定位"})
    elif FAKE_PAGE_RE.match(paragraph_id):
        issues.append({"type": "fake_pdf_page", "detail": "把自建页码当原文位置: %s" % paragraph_id})
    elif not jats_ok:
        issues.append({"type": "bad_anchor_format", "detail": "段落ID不是JATS格式: %s" % paragraph_id})

    if not quote:
        issues.append({"type": "no_quote", "detail": "缺原文短引，无法回查"})

    grounded = None
    quote_ok = None
    if source_index is not None and source_id and paragraph_id:
        grounded = _in_source(source_index, source_id, paragraph_id, surface)
        if grounded is False:
            issues.append({"type": "not_grounded", "severity": "warning",
                           "detail": "表面形式未在该段落原文出现，疑似凭常识补全"})
        if quote:
            quote_ok = _in_source(source_index, source_id, paragraph_id, quote)
            if quote_ok is False:
                issues.append({"type": "quote_mismatch", "severity": "warning",
                               "detail": "原文短引未在该段落命中"})

    identity_ok = attribution in AUTHOR_SELF or attribution in OTHER_REPORT
    if not identity_ok:
        issues.append({"type": "bad_attribution", "detail": "表述身份应为自述或转述: %s" % attribution})

    ok = (etype in ENTITY_TYPES and bool(surface) and bool(source_id) and jats_ok
          and bool(quote) and identity_ok and grounded is not False and quote_ok is not False)
    return {
        "id": entity.get("id", ""),
        "surface": surface, "type": etype, "type_zh": ENTITY_TYPE_ZH.get(etype, ""),
        "source_id": source_id, "paragraph_id": paragraph_id, "quote": quote,
        "attribution": ("self" if attribution in AUTHOR_SELF else
                        "other" if attribution in OTHER_REPORT else attribution),
        "grounded": grounded, "quote_in_source": quote_ok,
        "entity_ok": ok, "issues": issues,
    }


def extract_entities(entities: List[Dict[str, Any]],
                     source_index: Optional[Dict[str, Dict[str, str]]] = None,
                     known_papers: Optional[List[str]] = None) -> Dict[str, Any]:
    reports = [check_entity(e, source_index, known_papers) for e in (entities or [])]
    good = [r for r in reports if r["entity_ok"]]
    return {
        "checked": len(reports),
        "accepted": len(good),
        "rejected": len(reports) - len(good),
        "entities": reports,
        "rejected_ids": [r["id"] for r in reports if not r["entity_ok"]],
    }


# ---------------------------------------------------------------------------
# 连得对：关系
# ---------------------------------------------------------------------------
def check_relation(relation: Dict[str, Any],
                   entity_index: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """核验关系：类型/方向/条件合法，避免共现或推测当直接证据，跨篇关系需更强证据。"""
    issues: List[Dict[str, Any]] = []
    rtype = relation.get("relation") or relation.get("type", "")
    subj = relation.get("subject", "")
    obj = relation.get("object", "")
    ev_type = relation.get("evidence_type", "direct")
    quote = relation.get("quote", "") or relation.get("evidence", "")
    condition = relation.get("condition", "")
    source_id = relation.get("source_id", "")
    paragraph_id = relation.get("paragraph_id", "")
    cross_paper = bool(relation.get("cross_paper", False))

    if rtype not in RELATION_TYPES:
        issues.append({"type": "bad_relation_type", "detail": "关系类型不在受控词表: %s" % rtype})
    if not subj or not obj:
        issues.append({"type": "missing_endpoint", "detail": "关系缺主语或宾语"})
    if subj and obj and _norm(subj) == _norm(obj):
        issues.append({"type": "self_loop", "detail": "主语与宾语相同"})

    if ev_type in WEAK_EVIDENCE:
        issues.append({"type": "weak_evidence_as_relation", "severity": "error",
                       "detail": "共现/转述/推测/常识不能作为直接关系证据: %s" % ev_type})
    elif ev_type not in DIRECT_EVIDENCE:
        issues.append({"type": "bad_evidence_type", "detail": "非法证据类型: %s" % ev_type})

    if not quote:
        issues.append({"type": "no_quote", "detail": "关系缺原文短引"})
    if not paragraph_id or not JATS_ID_RE.match(paragraph_id or ""):
        issues.append({"type": "bad_anchor", "detail": "关系段落定位缺失或非JATS: %s" % paragraph_id})
    if FAKE_PAGE_RE.match(paragraph_id or ""):
        issues.append({"type": "fake_pdf_page", "detail": "不得把自建页码当原文位置"})

    # 适用条件：题面强调"适用条件"要与原文一致；此处要求显式声明
    if not condition:
        issues.append({"type": "no_condition", "severity": "warning",
                       "detail": "未声明适用条件（样本/条件/范围）"})

    # 端点存在性与跨篇检查
    endpoints_ok = True
    if entity_index is not None:
        endpoints_ok = (subj in entity_index) and (obj in entity_index)
        if not endpoints_ok:
            issues.append({"type": "dangling_endpoint", "detail": "关系端点不是已接受的实体节点"})
        else:
            s_src = (entity_index.get(subj) or {}).get("source_id", "")
            o_src = (entity_index.get(obj) or {}).get("source_id", "")
            if s_src and o_src and s_src != o_src and not cross_paper:
                issues.append({"type": "cross_paper_unmarked", "severity": "error",
                               "detail": "跨篇关系未显式标注 cross_paper，可能是把两篇条件拼成一个结论"})
            if cross_paper and ev_type not in DIRECT_EVIDENCE:
                issues.append({"type": "cross_paper_weak_evidence", "severity": "error",
                               "detail": "跨篇关系必须有直接证据，不能靠共现/推测"})

    # 方向性关系必须给出方向明确的表述（用 subject->object 已隐含，这里校验 direction 字段若给则合法）
    direction = relation.get("direction", "forward")
    if direction not in ("forward", "reverse", "symmetric"):
        issues.append({"type": "bad_direction", "detail": "方向取值应为 forward/reverse/symmetric"})

    ok = (rtype in RELATION_TYPES and bool(subj) and bool(obj) and _norm(subj) != _norm(obj)
          and ev_type in DIRECT_EVIDENCE and bool(quote)
          and bool(paragraph_id) and bool(JATS_ID_RE.match(paragraph_id or ""))
          and endpoints_ok and not any(i.get("severity") == "error" for i in issues))
    return {
        "id": relation.get("id", ""), "subject": subj, "relation": rtype, "object": obj,
        "direction": direction, "condition": condition, "evidence_type": ev_type,
        "quote": quote, "source_id": source_id, "paragraph_id": paragraph_id,
        "cross_paper": cross_paper, "relation_ok": ok, "issues": issues,
    }


def check_relations(relations: List[Dict[str, Any]],
                    entity_index: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    reports = [check_relation(r, entity_index) for r in (relations or [])]
    good = [r for r in reports if r["relation_ok"]]
    return {
        "checked": len(reports), "accepted": len(good), "rejected": len(reports) - len(good),
        "relations": reports,
        "rejected_ids": [r["id"] for r in reports if not r["relation_ok"]],
    }


# ---------------------------------------------------------------------------
# 对得齐：实体对齐（别名归一 + 跨篇同名冲突）
# ---------------------------------------------------------------------------
def align_entities(entities: List[Dict[str, Any]],
                   alias_rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    alias_rules: [{"canonical":"CNN", "aliases":["卷积神经网络","cnn","ConvNet"],
                   "source_ids":["S1"]}]  —— 可限定规则适用论文。
    规则：
      - 同篇内 surface 归一相同，或命中别名规则 -> 合并候选（给依据）。
      - 跨篇相同 surface：无规则明确声明同指 -> 一律不合并，列为 conflict（保留为不同节点）。
      - 即便命中规则，若类型或来源属性冲突 -> 也不合并。
    """
    rules = alias_rules or []
    # 建立别名 -> (canonical, 允许的 source_ids) 映射
    alias_map: Dict[str, tuple] = {}
    for rule in rules:
        canon = rule.get("canonical", "")
        allow = set(rule.get("source_ids", [])) or None
        for a in [canon] + list(rule.get("aliases", [])):
            alias_map.setdefault(_norm_loose(a), (canon, allow))

    # 关键：分组键在归一后取 canonical，使别名（字面不同）能在分组时即落到同一组
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for e in (entities or []):
        key = _norm_loose(e.get("surface", ""))
        hit = alias_map.get(key)
        ckey = _norm_loose(hit[0]) if hit else key
        groups.setdefault(ckey, []).append(e)

    merges: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    canonical_of: Dict[str, str] = {}   # entity id -> canonical id

    for ckey, members in groups.items():
        if len(members) < 2:
            continue
        sources = {m.get("source_id", "") for m in members}
        types = {m.get("type", "") for m in members}
        # 找覆盖本组的别名规则（任一成员命中即可）
        rule = None
        for m in members:
            hit = alias_map.get(_norm_loose(m.get("surface", "")))
            if hit:
                rule = hit
                break

        # 同名但类型不同 -> 不同对象，禁止合并
        if len(types) > 1:
            conflicts.append({"key": ckey, "reason": "type_conflict",
                              "surfaces": [m.get("surface", "") for m in members],
                              "sources": sorted(sources), "types": sorted(types),
                              "decision": "kept_separate"})
            continue

        # 跨篇：只有规则明确声明且未限定来源（或来源都被包含）才允许合并
        if len(sources) > 1:
            allowed = rule[1] if rule else None
            permitted = rule and (allowed is None or sources.issubset(allowed))
            if not permitted:
                conflicts.append({"key": ckey, "reason": "cross_paper_same_surface",
                                  "surfaces": [m.get("surface", "") for m in members],
                                  "sources": sorted(sources),
                                  "decision": "kept_separate",
                                  "note": "相同通用术语不代表两篇用了相同样品/模型/数据集/条件"})
                continue
            basis = "alias_rule"
        else:
            basis = "alias_rule" if rule else "same_paper_normalized"

        canonical = rule[0] if rule else members[0].get("surface", "")
        member_ids = [m.get("id", "") for m in members]
        merges.append({"canonical": canonical, "basis": basis,
                       "member_ids": member_ids, "sources": sorted(sources)})
        for mid in member_ids:
            canonical_of[mid] = canonical

    return {
        "merge_count": len(merges), "conflict_count": len(conflicts),
        "merges": merges, "conflicts": conflicts,
        "canonical_of": canonical_of,
        "node_count_after": len(entities or []) - sum(len(m["member_ids"]) - 1 for m in merges),
    }


def bind_source(item: Dict[str, Any],
                source_index: Optional[Dict[str, Dict[str, str]]] = None) -> Dict[str, Any]:
    """逐节点/边核验来源绑定：source_id + JATS 段落 ID + 原文短引三者齐备且可回查。"""
    issues: List[Dict[str, Any]] = []
    source_id = item.get("source_id", "")
    paragraph_id = item.get("paragraph_id", "")
    quote = item.get("quote", "") or item.get("evidence", "")
    if not source_id:
        issues.append({"type": "no_source_id", "detail": "缺论文标识"})
    if not paragraph_id or not JATS_ID_RE.match(paragraph_id or ""):
        issues.append({"type": "bad_anchor", "detail": "段落定位非JATS格式"})
    if FAKE_PAGE_RE.match(paragraph_id or ""):
        issues.append({"type": "fake_pdf_page", "detail": "不得用自建页码冒充原文位置"})
    if not quote:
        issues.append({"type": "no_quote", "detail": "缺原文短引"})

    quote_ok = None
    if source_index is not None and source_id and paragraph_id and quote:
        quote_ok = _in_source(source_index, source_id, paragraph_id, quote)
        if not quote_ok:
            issues.append({"type": "quote_mismatch", "severity": "warning",
                           "detail": "原文短引未在指定段落命中"})

    bound = (bool(source_id) and bool(paragraph_id)
             and bool(JATS_ID_RE.match(paragraph_id or ""))
             and bool(quote) and quote_ok is not False)
    return {"id": item.get("id", ""), "bound": bound, "quote_in_source": quote_ok,
            "source_id": source_id, "paragraph_id": paragraph_id, "quote": quote,
            "issues": issues}


# ---------------------------------------------------------------------------
# 查得到、回得去：图查询
# ---------------------------------------------------------------------------
def _neighbors(node_id: str, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for e in edges or []:
        if e.get("subject") == node_id or e.get("object") == node_id:
            out.append(e)
    return out


def query_graph(graph: Dict[str, Any], queries: List[Dict[str, Any]],
                source_index: Optional[Dict[str, Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    queries: [{"id":"Q1", "type":"entity"|"neighbor"|"relation", "surface"|"relation"|"keyword": ...}]
    每个答案带命中的结果子图与可回查证据；弱证据关系单列 unresolved（无法确定）。
    """
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    node_by_id = {n.get("id", ""): n for n in nodes}

    def _resolve(token: str) -> Optional[Dict[str, Any]]:
        """关系端点可能写 id，也可能写 surface；两种都要能解析回节点证据。"""
        if not token:
            return None
        if token in node_by_id:
            return node_by_id[token]
        nt = _norm(token)
        for n in nodes:
            if nt and nt == _norm(n.get("surface", "")):
                return n
        return None

    answers = []

    for q in (queries or []):
        qid = q.get("id", "")
        qtype = q.get("type", "entity")
        matched_nodes: List[str] = []
        matched_edges: List[Dict[str, Any]] = []
        unresolved: List[str] = []

        if qtype == "entity":
            kw = _norm(q.get("surface", "") or q.get("keyword", ""))
            for n in nodes:
                if kw and kw in _norm(n.get("surface", "")):
                    matched_nodes.append(n.get("id", ""))
        elif qtype == "relation":
            rt = q.get("relation", "")
            for e in edges:
                if e.get("relation") == rt:
                    matched_edges.append(e)
                    matched_nodes.extend([e.get("subject", ""), e.get("object", "")])
        elif qtype == "neighbor":
            # 种子用 node/surface 指定；q["id"] 是查询编号，绝不能当节点ID
            seed = q.get("node", "") or q.get("surface", "") or q.get("seed", "")
            seed_id = seed if seed in node_by_id else ""
            if not seed_id:
                for n in nodes:
                    if _norm(seed) and _norm(seed) == _norm(n.get("surface", "")):
                        seed_id = n.get("id", "")
                        break
            if seed_id:
                matched_nodes.append(seed_id)
                nb = _neighbors(seed_id, edges)
                for e in nb:
                    if e.get("evidence_type") in WEAK_EVIDENCE:
                        unresolved.append(e.get("id", ""))
                    else:
                        matched_edges.append(e)
                    matched_nodes.extend([e.get("subject", ""), e.get("object", "")])

        matched_nodes = list(dict.fromkeys([m for m in matched_nodes if m]))
        # 证据：从命中的节点/边收集 source_id + paragraph_id + quote，并可回查
        evidence = []
        for e in matched_edges:
            evidence.append({"kind": "edge", "id": e.get("id", ""),
                             "source_id": e.get("source_id", ""),
                             "paragraph_id": e.get("paragraph_id", ""),
                             "quote": e.get("quote", "")})
        for nid in matched_nodes:
            n = _resolve(nid) or {}
            evidence.append({"kind": "node", "id": nid,
                             "source_id": n.get("source_id", ""),
                             "paragraph_id": n.get("paragraph_id", ""),
                             "quote": n.get("quote", "")})
        traceable = all(bool(x["source_id"]) and bool(x["paragraph_id"]) and bool(x["quote"])
                        for x in evidence) if evidence else False
        if source_index is not None:
            for x in evidence:
                if x["source_id"] and x["paragraph_id"] and x["quote"]:
                    x["quote_in_source"] = _in_source(source_index, x["source_id"],
                                                      x["paragraph_id"], x["quote"])

        answers.append({
            "query_id": qid, "query_type": qtype, "query": q,
            "matched_nodes": matched_nodes,
            "matched_edges": [e.get("id", "") for e in matched_edges],
            "subgraph": {"nodes": matched_nodes,
                         "edges": [e.get("id", "") for e in matched_edges]},
            "evidence": evidence, "traceable": traceable,
            "unresolved_edges": unresolved,
            "has_answer": bool(matched_nodes or matched_edges),
        })

    answered = sum(1 for a in answers if a["has_answer"])
    return {
        "query_count": len(answers), "answered": answered,
        "min_three_queries": len(answers) >= 3,
        "all_traceable": bool(answers) and all(a["traceable"] for a in answers if a["has_answer"]),
        "answers": answers,
    }


# ---------------------------------------------------------------------------
# 增量更新：保留既有节点编号
# ---------------------------------------------------------------------------
def incremental_update(existing: Dict[str, Any],
                       incoming: Dict[str, Any],
                       alias_rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    新论文加入：保留既有节点与编号；同篇同表面/命中别名规则 -> 合并；跨篇相同表面 -> 保留冲突不合并。
    """
    old_nodes = list(existing.get("nodes", []) or [])
    old_edges = list(existing.get("edges", []) or [])
    new_nodes = list(incoming.get("nodes", []) or [])
    new_edges = list(incoming.get("edges", []) or [])

    rules = alias_rules or []
    alias_map = {}
    for r in rules:
        canon = r.get("canonical", "")
        for a in [canon] + list(r.get("aliases", [])):
            alias_map.setdefault(_norm_loose(a), canon)

    changes = {"added_nodes": [], "merged_nodes": [], "kept_conflicts": [],
               "added_edges": [], "skipped_edges": [], "renumbered": []}

    # 既有节点索引（保留原 id）
    nodes = [dict(n) for n in old_nodes]
    id_index = {n.get("id", ""): n for n in nodes}
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes:
        by_key.setdefault(_norm_loose(n.get("surface", "")), []).append(n)

    for nn in new_nodes:
        key = _norm_loose(nn.get("surface", ""))
        cand = by_key.get(key, [])
        canon_hit = alias_map.get(key)
        if canon_hit:
            for n in nodes:
                if _norm_loose(n.get("surface", "")) == _norm_loose(canon_hit):
                    cand = cand + [n]
        same_paper = [n for n in cand if n.get("source_id") == nn.get("source_id")]
        cross_paper = [n for n in cand if n.get("source_id") != nn.get("source_id")]

        if same_paper:
            target = same_paper[0]
            changes["merged_nodes"].append({"new_surface": nn.get("surface", ""),
                                            "into_id": target.get("id", ""),
                                            "basis": "same_paper_or_alias"})
            continue
        if cross_paper:
            changes["kept_conflicts"].append({"new_surface": nn.get("surface", ""),
                                              "conflict_with": [n.get("id", "") for n in cross_paper],
                                              "reason": "cross_paper_same_surface",
                                              "decision": "kept_separate"})
            # 作为独立新节点加入，分配新编号
        new_id = nn.get("id") or ("N%d" % (len(nodes) + 1))
        if new_id in id_index:
            new_id = "N%d" % (len(nodes) + 1)
        added = dict(nn); added["id"] = new_id
        nodes.append(added); id_index[new_id] = added
        by_key.setdefault(key, []).append(added)
        changes["added_nodes"].append({"id": new_id, "surface": nn.get("surface", ""),
                                       "source_id": nn.get("source_id", "")})

    # 边：端点必须存在，否则跳过；保留旧边，仅追加新边
    edges = [dict(e) for e in old_edges]
    existing_edge_ids = {e.get("id", "") for e in edges}
    for ne_ in new_edges:
        if ne_.get("subject") not in id_index or ne_.get("object") not in id_index:
            changes["skipped_edges"].append({"id": ne_.get("id", ""), "reason": "dangling_endpoint"})
            continue
        eid = ne_.get("id") or ("E%d" % (len(edges) + 1))
        if eid in existing_edge_ids:
            eid = "E%d" % (len(edges) + 1)
        added = dict(ne_); added["id"] = eid
        edges.append(added); existing_edge_ids.add(eid)
        changes["added_edges"].append({"id": eid, "relation": ne_.get("relation", "")})

    return {
        "node_count": len(nodes), "edge_count": len(edges),
        "existing_node_ids_preserved": all(
            n.get("id", "") in {x.get("id", "") for x in nodes} for n in old_nodes),
        "changes": changes,
        "graph": {"nodes": nodes, "edges": edges},
    }


# ---------------------------------------------------------------------------
# 导出检查
# ---------------------------------------------------------------------------
GRAPH_NODE_FIELDS = ["id", "surface", "type", "source_id", "paragraph_id", "quote"]
GRAPH_EDGE_FIELDS = ["id", "subject", "relation", "object", "evidence_type",
                     "source_id", "paragraph_id", "quote"]


def check_export(graph: Dict[str, Any], fmt: str = "json") -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    if fmt not in ("json", "jsonl", "graphml-json"):
        issues.append({"type": "bad_format", "detail": "导出格式应为 json/jsonl/graphml-json"})
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    missing_node = []
    missing_edge = []
    for n in nodes:
        miss = [f for f in GRAPH_NODE_FIELDS if not n.get(f)]
        if miss:
            missing_node.append({"id": n.get("id", ""), "fields": miss})
    for e in edges:
        miss = [f for f in GRAPH_EDGE_FIELDS if not e.get(f)]
        if miss:
            missing_edge.append({"id": e.get("id", ""), "fields": miss})
    ids = [n.get("id", "") for n in nodes]
    dup = sorted({x for x in ids if ids.count(x) > 1})
    serializable = True
    try:
        json.dumps(graph, ensure_ascii=False)
    except Exception:
        serializable = False
    ok = (not issues and not missing_node and not missing_edge and not dup and serializable)
    return {
        "format": fmt, "machine_readable": ok, "serializable": serializable,
        "node_count": len(nodes), "edge_count": len(edges),
        "missing_node_fields": missing_node, "missing_edge_fields": missing_edge,
        "duplicate_node_ids": dup, "issues": issues,
    }


# ---------------------------------------------------------------------------
# 端到端 pipeline
# ---------------------------------------------------------------------------
def coverage_check(graph: Dict[str, Any], query_result: Dict[str, Any]) -> Dict[str, Any]:
    """图谱完整度：实体/关系类型覆盖 + 至少 3 个真实可答查询。"""
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    ent_types = sorted({str(n.get("type", "")) for n in nodes if n.get("type")})
    rel_types = sorted({str(e.get("relation", "")) for e in edges if e.get("relation")})
    answers = query_result.get("answers", []) or []
    q_total = len(answers)
    q_answered = sum(1 for a in answers if a.get("has_answer"))
    q_traceable = sum(1 for a in answers if a.get("traceable"))
    issues = []
    if q_total < 3:
        issues.append({"type": "query_count_low", "severity": "critical",
                       "detail": f"仅 {q_total} 个查询，题面要求至少 3 个真实查询"})
    if q_total >= 3 and q_answered < 2:
        issues.append({"type": "query_no_answer", "severity": "major",
                       "detail": f"{q_total} 个查询中仅 {q_answered} 个有答案；无结果须如实说明，但不能全部落空"})
    if len(ent_types) < 3:
        issues.append({"type": "entity_type_thin", "severity": "warning",
                       "detail": f"实体类型仅 {ent_types}；建议覆盖方法/材料/任务/指标/结论中至少 3 类"})
    if len(rel_types) < 3:
        issues.append({"type": "relation_type_thin", "severity": "warning",
                       "detail": f"关系类型仅 {rel_types}；建议覆盖使用/比较/优于/支持/矛盾中至少 3 类"})
    if len(nodes) < 2 or len(edges) < 1:
        issues.append({"type": "graph_thin", "severity": "critical",
                       "detail": f"图谱仅 {len(nodes)} 节点 / {len(edges)} 边，至少需要 2 节点/1 边才能查询"})
    elif len(nodes) < 6 or len(edges) < 4:
        issues.append({"type": "graph_small", "severity": "warning",
                       "detail": f"图谱仅 {len(nodes)} 节点 / {len(edges)} 边；真实案例建议覆盖更多段落"})
    critical = [i for i in issues if i["severity"] == "critical"]
    ok = not critical and q_traceable == q_total and q_total >= 3 and len(nodes) >= 2 and len(edges) >= 1
    return {
        "ok": ok, "issues": issues, "entity_count": len(nodes), "edge_count": len(edges),
        "entity_types": ent_types, "relation_types": rel_types,
        "query_total": q_total, "query_answered": q_answered, "query_traceable": q_traceable,
        "note": "完整度是覆盖下限；实体/关系是否忠实、合并是否正确仍须回原文核对。",
    }


def pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    case_id = payload.get("case_id", "")
    source_index = payload.get("source_index") or {}
    known_papers = list(source_index.keys()) or payload.get("known_papers") or None
    entities = payload.get("entities", []) or []
    relations = payload.get("relations", []) or []
    alias_rules = payload.get("alias_rules", []) or []
    queries = payload.get("queries", []) or []

    r_ent = extract_entities(entities, source_index, known_papers if known_papers else None)
    entity_index = {r["surface"]: r for r in r_ent["entities"] if r["entity_ok"]}
    # 也用 id 建索引，便于关系端点用 id 指代
    for r in r_ent["entities"]:
        if r["entity_ok"] and r.get("id"):
            entity_index.setdefault(r["id"], r)

    r_rel = check_relations(relations, entity_index if known_papers else None)
    r_align = align_entities(entities, alias_rules)

    # 构建图（只纳入通过校验的节点/边）
    acc_nodes = [r for r in r_ent["entities"] if r["entity_ok"]]
    acc_edges = [r for r in r_rel["relations"] if r["relation_ok"]]
    graph = {"nodes": acc_nodes, "edges": acc_edges}

    r_bind = [bind_source(x, source_index) for x in acc_nodes + acc_edges]
    r_query = query_graph(graph, queries, source_index if source_index else None)
    r_export = check_export(graph, payload.get("export_format", "json"))
    r_cov = coverage_check(graph, r_query)

    # 增量更新（可选）
    r_incr = None
    if payload.get("incremental"):
        inc = payload["incremental"]
        r_incr = incremental_update(inc.get("existing", {}), inc.get("incoming", {}), alias_rules)
        graph = r_incr["graph"]
        r_export = check_export(graph, payload.get("export_format", "json"))
        r_cov = coverage_check(graph, r_query)

    overall = (r_ent["rejected"] == 0 and r_rel["rejected"] == 0
               and r_query["all_traceable"] and r_export["machine_readable"]
               and r_cov["ok"] and all(b["bound"] for b in r_bind))
    return {
        "case_id": case_id,
        "status": "ok" if overall else "needs_attention",
        "result": {
            "entity_extraction": r_ent,
            "relation_check": r_rel,
            "entity_alignment": r_align,
            "source_bindings": r_bind,
            "graph_query": r_query,
            "export_check": r_export,
            "coverage_check": r_cov,
            "incremental_update": r_incr,
            "graph": graph,
        },
        "evidence": {
            "principles": {
                "抽得准": "实体真在论文出现、类型合法、保留JATS位置与原文、区分自述/转述",
                "连得对": "关系类型/方向/条件与原文一致，共现与推测不作直接证据",
                "对得齐": "别名归一给依据，跨篇同名保留为不同节点",
                "查得到回得去": "每个查询结果子图可回到论文段落与原文短引",
            },
            "rejected_entities": r_ent["rejected_ids"],
            "rejected_relations": r_rel["rejected_ids"],
            "cross_paper_conflicts": [c for c in r_align["conflicts"]
                                      if c.get("reason") == "cross_paper_same_surface"],
            "unbound_items": [b["id"] for b in r_bind if not b["bound"]],
        },
        "uncertainty": {
            "needs_review": (r_ent["rejected_ids"] + r_rel["rejected_ids"]
                             + [c.get("key", "") for c in r_align["conflicts"]]),
            "note": ("实体/关系是否忠实、别名是否真同指、证据是否支撑属价值判断，须 Agent 结合原文复核；"
                     "脚本只做结构与规则校验，不臆造实体、关系、证据或来源；位置均为JATS段落ID而非PDF页码"),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="文献知识图谱构建确定性引擎")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("extract-entities", help="抽得准").add_argument("input")
    sub.add_parser("check-relations", help="连得对").add_argument("input")
    sub.add_parser("align-entities", help="对得齐").add_argument("input")
    sub.add_parser("bind-source", help="来源绑定").add_argument("input")
    sub.add_parser("query-graph", help="查得到回得去").add_argument("input")
    sub.add_parser("incremental-update", help="增量更新").add_argument("input")
    sub.add_parser("check-export", help="导出检查").add_argument("input")
    sub.add_parser("pipeline", help="端到端").add_argument("input")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help(); return 0
    d = _load(args.input)
    if args.cmd == "extract-entities":
        out = extract_entities(d.get("entities", []), d.get("source_index"), d.get("known_papers"))
    elif args.cmd == "check-relations":
        out = check_relations(d.get("relations", []), d.get("entity_index"))
    elif args.cmd == "align-entities":
        out = align_entities(d.get("entities", []), d.get("alias_rules"))
    elif args.cmd == "bind-source":
        out = bind_source(d.get("item", {}), d.get("source_index"))
    elif args.cmd == "query-graph":
        out = query_graph(d.get("graph", {}), d.get("queries", []), d.get("source_index"))
    elif args.cmd == "incremental-update":
        out = incremental_update(d.get("existing", {}), d.get("incoming", {}), d.get("alias_rules"))
    elif args.cmd == "check-export":
        out = check_export(d.get("graph", {}), d.get("format", "json"))
    elif args.cmd == "pipeline":
        out = pipeline(d)
    else:
        p.print_help(); return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
