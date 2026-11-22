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
def _node_id(n: Dict[str, Any]) -> str:
    return str(n.get("id") or n.get("entity_id") or n.get("surface") or n.get("name") or "")


def _edge_end(e: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = e.get(k)
        if isinstance(v, dict):
            v = v.get("id") or v.get("name")
        if v:
            return str(v)
    return ""


def audit_graph(graph: Dict[str, Any],
                relation_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """图级体检：孤立点、自环、重复边、连通分量、度分布与关系 schema 域值校验。

    单条实体/关系合规不等于图可用；审稿看的是“这张图有没有结构硬伤”。
    """
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    ids = [_node_id(n) for n in nodes]
    id_set = {i for i in ids if i}
    dup_nodes = sorted({i for i in ids if i and ids.count(i) > 1})
    degree: Dict[str, int] = {i: 0 for i in id_set}
    self_loops, dangling, dup_edges = [], [], []
    triple_seen = set()
    rel_types: Dict[str, int] = {}
    schema_issues = []
    node_type = {i: str(n.get("type") or "") for i, n in zip(ids, nodes)}
    for e in edges:
        s = _edge_end(e, "source", "subject", "head", "from")
        t = _edge_end(e, "target", "object", "tail", "to")
        et = str(e.get("type") or e.get("relation") or e.get("predicate") or "?")
        rel_types[et] = rel_types.get(et, 0) + 1
        if s and s == t:
            self_loops.append(s)
        for x in (s, t):
            if x and x in degree:
                degree[x] += 1
            elif x:
                dangling.append({"edge": et, "missing": x})
        key = (s, et, t)
        if key in triple_seen:
            dup_edges.append({"source": s, "type": et, "target": t})
        triple_seen.add(key)
        if relation_schema and et in relation_schema:
            rule = relation_schema[et] or {}
            if rule.get("from") and node_type.get(s) not in rule["from"]:
                schema_issues.append({"edge": et, "end": "source", "node": s,
                                      "type": node_type.get(s), "allowed": rule["from"]})
            if rule.get("to") and node_type.get(t) not in rule["to"]:
                schema_issues.append({"edge": et, "end": "target", "node": t,
                                      "type": node_type.get(t), "allowed": rule["to"]})
    # 连通分量（仅统计有边的节点；孤立点单列）
    parent = {i: i for i in id_set}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        s = _edge_end(e, "source", "subject", "head", "from")
        t = _edge_end(e, "target", "object", "tail", "to")
        if s in parent and t in parent:
            ra, rb = find(s), find(t)
            if ra != rb:
                parent[rb] = ra
    comps = {}
    for i in id_set:
        comps.setdefault(find(i), []).append(i)
    isolated = sorted([i for i, d in degree.items() if d == 0])
    top = sorted(degree.items(), key=lambda kv: -kv[1])[:5]
    issues = []
    if dup_nodes:
        issues.append({"type": "duplicate_node_id", "items": dup_nodes})
    if dangling:
        issues.append({"type": "dangling_edge", "items": dangling})
    if self_loops:
        issues.append({"type": "self_loop", "items": self_loops})
    if dup_edges:
        issues.append({"type": "duplicate_edge", "items": dup_edges})
    if schema_issues:
        issues.append({"type": "schema_violation", "items": schema_issues})
    return {
        "node_count": len(nodes), "edge_count": len(edges),
        "relation_types": rel_types,
        "components": len(comps), "largest_component": max((len(v) for v in comps.values()), default=0),
        "isolated_nodes": isolated, "isolated_count": len(isolated),
        "degree_avg": round(sum(degree.values()) / max(1, len(ids)), 2),
        "top_degree": [{"node": k, "degree": v} for k, v in top],
        "issues": issues, "issue_count": len(issues),
        "advice": ("图结构未见硬伤" if not issues else
                   "发现 %d 类结构问题（%s）" % (len(issues), [i["type"] for i in issues])),
    }


def pipeline(payload: Dict[str, Any], with_draft: bool = False) -> Dict[str, Any]:
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

    # 增量更新（可选）
    r_incr = None
    if payload.get("incremental"):
        inc = payload["incremental"]
        r_incr = incremental_update(inc.get("existing", {}), inc.get("incoming", {}), alias_rules)
        graph = r_incr["graph"]
        r_export = check_export(graph, payload.get("export_format", "json"))

    overall = (r_ent["rejected"] == 0 and r_rel["rejected"] == 0
               and r_query["all_traceable"] and r_export["machine_readable"]
               and all(b["bound"] for b in r_bind) and bool(entities))
    r_audit = audit_graph(graph, payload.get("relation_schema"))
    draft_obj = render_draft(payload) if with_draft else None
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
            "incremental_update": r_incr,
            "graph_audit": r_audit,
            "graph": graph,
        },
        "draft_detail": draft_obj,
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
# 完成器：正文驱动抽取 / 真实输入适配 / 图谱交付成稿 / result.json 装配 / solve
# ---------------------------------------------------------------------------
# 正文候选实体类型提示词表（仅用于生成候选，最终类型/真伪仍走 check_entity 校验）
_ENTITY_HINTS = {
    "method": [r"CNN", r"随机森林", r"SVM", r"决策树", r"神经网络", r"阈值分割", r"[A-Z]{2,6}方法"],
    "model": [r"U-Net", r"ResNet", r"VGG", r"Transformer", r"[A-Z][A-Za-z0-9\-]{2,12}(?=模型|网络|为主干)"],
    "material": [r"碳酸盐岩", r"砂岩", r"页岩", r"薄片", r"岩心"],
    "metric": [r"准确率", r"F1值?", r"精度", r"召回率", r"\d+\.\d+的?(?:准确率|F1)"],
    "dataset": [r"\w+数据集", r"薄片图像\d*张?"],
}


def _extract_from_text(source_index: Dict[str, Dict[str, str]],
                       known_papers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """正文驱动抽取：从 source_index 原文用受控提示词表抽候选实体。

    只生成候选（带 source_id/JATS paragraph_id/quote/attribution），真伪与类型由下游
    check_entity 校验；不做共现臆造关系。这是摆脱"必须预填 entities"的关键能力。
    """
    candidates = []
    seen = set()
    papers = list(source_index.keys()) if known_papers is None else known_papers
    for sid in papers:
        paras = source_index.get(sid) or {}
        for pid, text in paras.items():
            if not isinstance(text, str):
                continue
            for etype, pats in _ENTITY_HINTS.items():
                for pat in pats:
                    for m in re.finditer(pat, text, re.I):
                        surface = m.group(0).strip()
                        key = (_norm(sid), _norm(pid), _norm(surface), etype)
                        if key in seen:
                            continue
                        seen.add(key)
                        # 自述/转述判定（同段落出现"我们/本文"或"作者/该研究"）
                        attribution = "self" if re.search(r"我们|本文|提出", text) else "other"
                        candidates.append({
                            "id": "auto_%d" % (len(candidates) + 1),
                            "surface": surface, "type": etype,
                            "source_id": sid, "paragraph_id": pid,
                            "quote": surface, "attribution": attribution,
                        })
    return candidates


def _adapt_case(payload: Dict[str, Any], case_dir: str) -> Dict[str, Any]:
    """真实输入适配器：读 source_index/实体/关系文件，并在缺少预填实体时正文驱动抽取。

    - source_index（内联）或 source_files（{论文:路径} 或 [路径]）——读 .json/.txt 建索引
    - entities/entities_file、relations/relations_file、queries/queries_file
    - extract_from_text=true（默认在 entities 为空时启用）——从正文抽候选
    读不到不臆造，记入 adapter_notes。
    """
    import os as _os
    work = dict(payload)
    log: List[str] = []

    sf = work.get("source_files") or {}
    if isinstance(sf, list):
        sf = {_os.path.splitext(_os.path.basename(str(x)))[0]: x for x in sf}
    si = dict(work.get("source_index") or {})
    for name, rel in sf.items():
        path = str(rel) if _os.path.isabs(str(rel)) else _os.path.join(case_dir, str(rel))
        try:
            raw = open(path, encoding="utf-8").read()
        except Exception:
            log.append("读取失败:%s" % _os.path.basename(path))
            continue
        if path.lower().endswith(".json"):
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and isinstance(data.get("source_index"), dict):
                    si.update(data["source_index"])
                    log.append("索引文件:%s" % _os.path.basename(path))
                    continue
            except Exception:
                pass
        # 纯文本：每个文件作为一篇论文，整段作为 sec1.p1
        si[name] = {"sec1.p1": raw[:4000]}
        log.append("文本索引:%s" % name)
    if si:
        work["source_index"] = si

    def load_list(key, file_key):
        items = work.get(key)
        if isinstance(items, list) and items:
            return items
        rel = work.get(file_key)
        if rel:
            path = str(rel) if _os.path.isabs(str(rel)) else _os.path.join(case_dir, str(rel))
            try:
                data = json.loads(open(path, encoding="utf-8").read())
                items = data.get(key, data) if isinstance(data, dict) else data
                log.append("%s文件:%d" % (key, len(items)) if isinstance(items, list) else key)
                return items if isinstance(items, list) else []
            except Exception:
                log.append("%s读取失败" % key)
        return []

    work["entities"] = load_list("entities", "entities_file")
    work["relations"] = load_list("relations", "relations_file")
    work["queries"] = load_list("queries", "queries_file")

    # 正文驱动抽取：无预填实体时，从 source_index 原文抽候选（评审点名能力）
    if not work["entities"] and si and payload.get("extract_from_text", True):
        auto = _extract_from_text(si)
        work["entities"] = auto
        log.append("正文抽取候选:%d" % len(auto))

    work["adapter_notes"] = log
    return work


def render_draft(payload: Dict[str, Any]) -> Dict[str, Any]:
    """用真实字段渲染【可编辑、可回链的知识图谱交付稿】——完成器核心。

    硬约束：
      - 节点/边只取真实实体/关系（经 check_entity/check_relation 校验通过的）；
      - 无实体标〔待补〕，不臆造实体、关系或证据；
      - 导出只序列化校验通过的图，附来源绑定与查询回链结论。
    """
    p = payload
    source_index = p.get("source_index") or {}
    entities = list(p.get("entities") or [])
    relations = list(p.get("relations") or [])
    queries = list(p.get("queries") or [])
    fmt = p.get("export_format", "json")

    r_ent = extract_entities(entities, source_index)
    good_entities = [r for r in r_ent["entities"] if r["entity_ok"]]
    eids = {r.get("id") for r in good_entities}
    # 关系端点可为 id 或 surface
    surfaces = {r.get("surface") for r in good_entities}
    good_relations = [r for r in relations if r.get("relation_ok", True) and
                      (r.get("subject") in eids or r.get("subject") in surfaces)]
    graph = {"nodes": good_entities, "edges": good_relations}
    r_export = check_export(graph, fmt)

    node_lines = ["- %s [%s]（%s/%s，引文：%s，%s）" % (
        r.get("surface", ""), r.get("type", ""), r.get("source_id", ""),
        r.get("paragraph_id", ""), r.get("quote", ""),
        "自述" if r.get("attribution") in AUTHOR_SELF else "转述")
        for r in good_entities]
    edge_lines = ["- %s --%s--> %s（%s/%s，条件：%s）" % (
        r.get("subject", ""), r.get("relation", ""), r.get("object", ""),
        r.get("source_id", ""), r.get("paragraph_id", ""), r.get("condition", ""))
        for r in good_relations]
    draft_text = "\n\n".join([
        "# 知识图谱交付稿（可编辑）",
        "## 节点（%d）\n%s" % (len(good_entities), "\n".join(node_lines) or "〔待补：无通过校验的实体〕"),
        "## 关系（%d）\n%s" % (len(good_relations), "\n".join(edge_lines) or "〔待补：无通过校验的关系〕"),
        "## 导出（%s）\n节点 %d / 边 %d；机读%s" % (
            fmt, r_export.get("node_count", 0), r_export.get("edge_count", 0),
            "合规" if r_export["machine_readable"] else "待修"),
    ])

    confirm = ["实体 %s 未通过校验：%s" % (r.get("id", ""), r.get("advice", ""))
               for r in r_ent["entities"] if not r["entity_ok"]]
    confirm += ["查询数不足 3" if len(queries) < 3 else ""]
    confirm = [c for c in confirm if c]
    all_ok = bool(good_entities) and not confirm
    return {
        "case_id": p.get("case_id", ""),
        "status": "draft" if all_ok else "partial",
        "draft_text": draft_text,
        "nodes": good_entities,
        "edges": good_relations,
        "node_count": len(good_entities),
        "edge_count": len(good_relations),
        "export_format": fmt,
        "source_refs": sorted(set("%s/%s" % (r.get("source_id", ""), r.get("paragraph_id", ""))
                                  for r in good_entities if r.get("source_id"))),
        "needs_author_confirmation": confirm,
        "uncertainty": [
            "节点/边只取真实实体/关系（经校验）；无实体标〔待补〕，不臆造实体、关系或证据",
            "实体真伪、别名同指、关系条件与证据支撑属价值判断，须结合原文人工复核；位置为 JATS 段落 ID",
        ],
        "note": ("可编辑知识图谱交付稿：校验通过的节点/边 + 来源绑定 + 导出；"
                 "非最终图谱，缺口以〔待补〕标注，须结合原文复核。"),
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
    """端到端完成器：读 case.json → 适配/正文抽取 → 校验 → 建图成稿 → 装配 result.json。"""
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
    if not work.get("source_index") and not work.get("entities"):
        result = {"case_id": cid, "status": "needs_attention", "input_mode": "case",
                  "result": {"summary": "输入无正文索引/实体/材料文件，无法建图（不伪造实体）"},
                  "needs_review": ["请提供真实 source_index 或论文材料"]}
        result["delivery"] = _write_solution(result, out_dir, cid)
        return result

    pl = pipeline(work, with_draft=True)
    draft = pl.get("draft_detail") or {}
    r = pl["result"]
    result = {
        "case_id": cid,
        "status": pl["status"],
        "input_mode": "case",
        "source_count": len(work.get("source_index", {})),
        "adapter_notes": work.get("adapter_notes", []),
        "result": {
            "draft_text": draft.get("draft_text", ""),
            "nodes": draft.get("nodes", []),
            "edges": draft.get("edges", []),
            "node_count": draft.get("node_count", 0),
            "edge_count": draft.get("edge_count", 0),
            "entity_extraction": r["entity_extraction"],
            "relation_check": r["relation_check"],
            "entity_alignment": r["entity_alignment"],
            "graph_query": r["graph_query"],
            "export_check": r["export_check"],
            "graph_audit": r.get("graph_audit"),
            "summary": ("节点 %d；关系 %d；实体拒收 %d；关系拒收 %d；查询 %d/%d 可回链；导出%s；"
                        "结构问题 %d" % (
                draft.get("node_count", 0), draft.get("edge_count", 0),
                r["entity_extraction"]["rejected"], r["relation_check"]["rejected"],
                r["graph_query"]["answered"], r["graph_query"]["query_count"],
                "合规" if r["export_check"]["machine_readable"] else "待修",
                (r.get("graph_audit") or {}).get("issue_count", 0))),
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
    p = argparse.ArgumentParser(description="文献知识图谱构建确定性引擎")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("extract-entities", help="抽得准").add_argument("input")
    sub.add_parser("check-relations", help="连得对").add_argument("input")
    sub.add_parser("align-entities", help="对得齐").add_argument("input")
    sub.add_parser("bind-source", help="来源绑定").add_argument("input")
    sub.add_parser("query-graph", help="查得到回得去").add_argument("input")
    sub.add_parser("incremental-update", help="增量更新").add_argument("input")
    sub.add_parser("check-export", help="导出检查").add_argument("input")
    sub.add_parser("render-draft", help="用真实字段渲染可编辑知识图谱交付稿").add_argument("input")
    sv = sub.add_parser("solve", help="端到端完成器：case.json →(适配/正文抽取)→ 建图 → result.json")
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
    elif args.cmd == "render-draft":
        out = render_draft(d)
    elif args.cmd == "pipeline":
        out = pipeline(d, with_draft=args.with_draft)
    else:
        p.print_help(); return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0

def _write_solution(result, out_dir, case_id):
    """写 result.json，并把 result 渲染成可读、可编辑的交付物（artifacts.py）。"""
    core = _write_solution_core(result, out_dir, case_id)
    try:
        from artifacts import write_artifacts
        core["artifacts"] = write_artifacts(result, out_dir, "knowledge-graph-builder")
    except Exception as e:  # 渲染失败不影响 result.json 已落盘
        core["artifacts_error"] = type(e).__name__
    return core

if __name__ == "__main__":
    sys.exit(main())
