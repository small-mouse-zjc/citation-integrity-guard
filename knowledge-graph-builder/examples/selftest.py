#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 第10关 文献知识图谱构建 Skill 自验收测试
覆盖：抽得准、连得对、对得齐、查得到回得去、来源绑定、增量更新、导出、pipeline。
运行：python examples/selftest.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import kg_engine as kg

FAILS = []
TOTAL = 0


def check(name, cond, detail=""):
    global TOTAL
    TOTAL += 1
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        FAILS.append(name)


# 模拟两篇独立论文的段落原文（JATS 段落 ID -> 文本）
SRC = {
    "S1": {
        "sec2.p3": "本文提出CNN方法在碳酸盐岩薄片图像上达到0.92准确率。",
        "sec3.p1": "作者将该模型应用于 sandstone 数据集并与 SVM 比较。",
        "sec4.p2": "该CNN使用U-Net架构。",
    },
    "S2": {
        "sec1.p2": "我们报告CNN方法在另一批页岩样本上取得0.85的F1值。",
        "sec2.p1": "该研究采用随机森林作为对比基线。",
        "sec5.p1": "结果显示该方法优于传统阈值分割。",
    },
}
KNOWN = ["S1", "S2"]

# ---------------- 抽得准 ----------------
e_good = {"id": "n1", "surface": "CNN", "type": "method", "source_id": "S1",
          "paragraph_id": "sec2.p3", "quote": "CNN方法", "attribution": "self"}
r = kg.check_entity(e_good, SRC, KNOWN)
check("T1 合法实体通过且落地原文", r["entity_ok"] and r["grounded"] is True and r["quote_in_source"] is True)

e_hallu = dict(e_good, id="n2", surface="Transformer", paragraph_id="sec2.p3", quote="Transformer")
r = kg.check_entity(e_hallu, SRC, KNOWN)
check("T2 未出现的实体被标 not_grounded", any(i["type"] == "not_grounded" for i in r["issues"]) and not r["entity_ok"])

e_type = dict(e_good, id="n3", type="幻想类型")
r = kg.check_entity(e_type, SRC, KNOWN)
check("T3 非法实体类型被拒", any(i["type"] == "bad_entity_type" for i in r["issues"]))

e_page = dict(e_good, id="n4", paragraph_id="page 1")
r = kg.check_entity(e_page, SRC, KNOWN)
check("T4 伪PDF页码被拒", any(i["type"] == "fake_pdf_page" for i in r["issues"]) and not r["entity_ok"])

e_src = dict(e_good, id="n5", source_id="S9")
r = kg.check_entity(e_src, SRC, KNOWN)
check("T5 未知来源被拒", any(i["type"] == "unknown_source_id" for i in r["issues"]))

e_other = dict(e_good, id="n6", attribution="cited", source_id="S1")
r = kg.check_entity(e_other, SRC, KNOWN)
check("T6 转述身份被区分", r["attribution"] == "other")

e_badattr = dict(e_good, id="n7", attribution="maybe")
r = kg.check_entity(e_badattr, SRC, KNOWN)
check("T7 非法表述身份被拒", any(i["type"] == "bad_attribution" for i in r["issues"]))

ents = kg.extract_entities([e_good, e_hallu, e_type], SRC, KNOWN)
check("T8 批量抽取计数正确", ents["checked"] == 3 and ents["accepted"] == 1 and ents["rejected"] == 2)

# ---------------- 连得对 ----------------
eidx = {"CNN": kg.check_entity(e_good, SRC, KNOWN),
        "SVM": kg.check_entity({"id": "n8", "surface": "SVM", "type": "model", "source_id": "S1",
                                "paragraph_id": "sec3.p1", "quote": "SVM", "attribution": "self"}, SRC, KNOWN)}

rel_good = {"id": "e1", "subject": "CNN", "relation": "compares", "object": "SVM",
            "evidence_type": "direct", "quote": "与 SVM 比较", "condition": "sandstone数据集",
            "source_id": "S1", "paragraph_id": "sec3.p1", "cross_paper": False}
r = kg.check_relation(rel_good, eidx)
check("T9 合法直接关系通过", r["relation_ok"])

rel_coo = dict(rel_good, id="e2", evidence_type="cooccurrence")
r = kg.check_relation(rel_coo, eidx)
check("T10 共现不能当直接关系", any(i["type"] == "weak_evidence_as_relation" for i in r["issues"]) and not r["relation_ok"])

rel_hearsay = dict(rel_good, id="e3", evidence_type="hearsay")
r = kg.check_relation(rel_hearsay, eidx)
check("T11 综述转述不能当直接关系", any(i["type"] == "weak_evidence_as_relation" for i in r["issues"]))

rel_badtype = dict(rel_good, id="e4", relation="causes_magic")
r = kg.check_relation(rel_badtype, eidx)
check("T12 非法关系类型被拒", any(i["type"] == "bad_relation_type" for i in r["issues"]))

rel_dangle = dict(rel_good, id="e5", object="不存在的实体")
r = kg.check_relation(rel_dangle, eidx)
check("T13 悬空端点被拒", any(i["type"] == "dangling_endpoint" for i in r["issues"]))

rel_self = dict(rel_good, id="e6", object="CNN")
r = kg.check_relation(rel_self, eidx)
check("T14 自环关系被拒", any(i["type"] == "self_loop" for i in r["issues"]))

rel_nocond = dict(rel_good, id="e7", condition="")
r = kg.check_relation(rel_nocond, eidx)
check("T15 未声明适用条件有告警", any(i["type"] == "no_condition" for i in r["issues"]))

# 跨篇关系未标注 / 弱证据
cross_eidx = {
    "CNN": kg.check_entity(e_good, SRC, KNOWN),
    "CNN2": kg.check_entity({"id": "n9", "surface": "CNN", "type": "method", "source_id": "S2",
                             "paragraph_id": "sec1.p2", "quote": "CNN方法", "attribution": "self"}, SRC, KNOWN),
}
rel_cross = {"id": "e8", "subject": "CNN", "relation": "supports", "object": "CNN2",
             "evidence_type": "direct", "quote": "CNN方法", "condition": "跨篇",
             "source_id": "S1", "paragraph_id": "sec2.p3", "cross_paper": False}
r = kg.check_relation(rel_cross, cross_eidx)
check("T16 跨篇关系未标注被拒", any(i["type"] == "cross_paper_unmarked" for i in r["issues"]) and not r["relation_ok"])

rel_cross_weak = dict(rel_cross, cross_paper=True, evidence_type="cooccurrence")
r = kg.check_relation(rel_cross_weak, cross_eidx)
check("T17 跨篇弱证据关系被拒", any(i["type"] == "cross_paper_weak_evidence" for i in r["issues"]))

rel_cross_ok = dict(rel_cross, cross_paper=True)
r = kg.check_relation(rel_cross_ok, cross_eidx)
check("T18 跨篇直接证据关系可通过", r["relation_ok"])

rels = kg.check_relations([rel_good, rel_coo], eidx)
check("T19 批量关系计数正确", rels["checked"] == 2 and rels["accepted"] == 1)

# ---------------- 对得齐 ----------------
# 同篇别名 -> 合并；跨篇相同surface -> 不合并
alias = [{"canonical": "CNN", "aliases": ["卷积神经网络", "ConvNet"], "source_ids": ["S1"]}]
same_paper = [
    {"id": "a1", "surface": "CNN", "type": "method", "source_id": "S1"},
    {"id": "a2", "surface": "卷积神经网络", "type": "method", "source_id": "S1"},
]
out = kg.align_entities(same_paper, alias)
check("T20 同篇别名被合并", out["merge_count"] == 1 and out["canonical_of"].get("a2") == "CNN")

cross_same = [
    {"id": "b1", "surface": "CNN", "type": "method", "source_id": "S1"},
    {"id": "b2", "surface": "CNN", "type": "method", "source_id": "S2"},
]
out = kg.align_entities(cross_same, [])
check("T21 跨篇相同surface不合并", out["merge_count"] == 0 and out["conflict_count"] == 1 and
      out["conflicts"][0]["reason"] == "cross_paper_same_surface")

# 跨篇即便命中别名规则也不合并（规则仅适用S1）
out = kg.align_entities(cross_same, alias)
check("T22 跨篇命中规则仍保留冲突", out["merge_count"] == 0 and out["conflict_count"] == 1)

# 同名不同类型 -> 冲突不合并
type_conflict = [
    {"id": "c1", "surface": "CNN", "type": "method", "source_id": "S1"},
    {"id": "c2", "surface": "CNN", "type": "model", "source_id": "S1"},
]
out = kg.align_entities(type_conflict, [])
check("T23 同名不同类型不合并", any(c["reason"] == "type_conflict" for c in out["conflicts"]))

# 跨篇别名规则显式允许两篇 -> 可合并
alias_both = [{"canonical": "CNN", "aliases": ["ConvNet"], "source_ids": ["S1", "S2"]}]
cross_alias = [
    {"id": "d1", "surface": "CNN", "type": "method", "source_id": "S1"},
    {"id": "d2", "surface": "ConvNet", "type": "method", "source_id": "S2"},
]
out = kg.align_entities(cross_alias, alias_both)
check("T24 显式双篇别名规则可合并", out["merge_count"] == 1)

# ---------------- 来源绑定 ----------------
b_ok = kg.bind_source({"id": "x", "source_id": "S1", "paragraph_id": "sec2.p3", "quote": "CNN方法"}, SRC)
check("T25 来源绑定通过", b_ok["bound"] and b_ok["quote_in_source"] is True)
b_bad = kg.bind_source({"id": "y", "source_id": "S1", "paragraph_id": "sec2.p3", "quote": "不存在的话"}, SRC)
check("T26 原文短引不匹配被标记", any(i["type"] == "quote_mismatch" for i in b_bad["issues"]))
b_page = kg.bind_source({"id": "z", "source_id": "S1", "paragraph_id": "第1页", "quote": "CNN方法"}, SRC)
check("T27 来源绑定拒伪页码", any(i["type"] == "fake_pdf_page" for i in b_page["issues"]) and not b_page["bound"])

# ---------------- 查得到、回得去 ----------------
graph = {
    "nodes": [
        {"id": "n1", "surface": "CNN", "type": "method", "source_id": "S1", "paragraph_id": "sec2.p3", "quote": "CNN方法"},
        {"id": "n2", "surface": "SVM", "type": "model", "source_id": "S1", "paragraph_id": "sec3.p1", "quote": "SVM"},
    ],
    "edges": [
        {"id": "e1", "subject": "n1", "relation": "compares", "object": "n2", "evidence_type": "direct",
         "source_id": "S1", "paragraph_id": "sec3.p1", "quote": "与 SVM 比较"},
    ],
}
queries = [
    {"id": "Q1", "type": "entity", "surface": "CNN"},
    {"id": "Q2", "type": "relation", "relation": "compares"},
    {"id": "Q3", "type": "neighbor", "node": "n1"},
]
out = kg.query_graph(graph, queries, SRC)
check("T28 三查询均执行", out["query_count"] == 3 and out["min_three_queries"])
check("T29 查询有答案且可回查", out["answered"] == 3 and out["all_traceable"])

# 弱证据关系单列 unresolved
graph2 = {"nodes": graph["nodes"], "edges": [dict(graph["edges"][0], id="e2", evidence_type="cooccurrence")]}
out2 = kg.query_graph(graph2, [{"id": "Q4", "type": "neighbor", "node": "n1"}], SRC)
check("T30 弱证据关系进unresolved", "e2" in out2["answers"][0]["unresolved_edges"])

# ---------------- 增量更新 ----------------
existing = {
    "nodes": [{"id": "N1", "surface": "CNN", "type": "method", "source_id": "S1",
               "paragraph_id": "sec2.p3", "quote": "CNN方法"}],
    "edges": [],
}
incoming = {
    "nodes": [
        {"id": "tmp", "surface": "CNN", "type": "method", "source_id": "S1",
         "paragraph_id": "sec3.p1", "quote": "该CNN"},          # 同篇 -> 合并
        {"id": "tmp2", "surface": "CNN", "type": "method", "source_id": "S2",
         "paragraph_id": "sec1.p2", "quote": "CNN方法"},        # 跨篇 -> 保留独立
        {"id": "tmp3", "surface": "RandomForest", "type": "model", "source_id": "S2",
         "paragraph_id": "sec2.p1", "quote": "随机森林"},       # 新增
    ],
    "edges": [{"id": "newe", "subject": "N1", "relation": "compares", "object": "tmp3",
               "evidence_type": "direct", "source_id": "S2", "paragraph_id": "sec2.p1", "quote": "对比基线"}],
}
out = kg.incremental_update(existing, incoming, [])
check("T31 增量保留既有编号", out["existing_node_ids_preserved"] and "N1" in {n["id"] for n in out["graph"]["nodes"]})
check("T32 增量同篇合并/跨篇保留冲突", len(out["changes"]["merged_nodes"]) == 1 and
      len(out["changes"]["kept_conflicts"]) == 1)
check("T33 增量新增节点与边", len(out["changes"]["added_nodes"]) == 2 and len(out["changes"]["added_edges"]) == 1)

# ---------------- 导出 ----------------
ex = kg.check_export(graph, "json")
check("T34 合规图谱导出通过", ex["machine_readable"] and ex["serializable"] and not ex["duplicate_node_ids"])
ex_bad = kg.check_export({"nodes": [{"id": "n1", "surface": "CNN"}], "edges": []}, "json")
check("T35 缺字段导出被检出", len(ex_bad["missing_node_fields"]) >= 1 and not ex_bad["machine_readable"])
ex_fmt = kg.check_export(graph, "pdf")
check("T36 非法导出格式被检出", any(i["type"] == "bad_format" for i in ex_fmt["issues"]))

# ---------------- pipeline ----------------
payload = {
    "case_id": "CASE-KG-01", "source_index": SRC,
    "entities": [e_good,
                 {"id": "n8", "surface": "SVM", "type": "model", "source_id": "S1",
                  "paragraph_id": "sec3.p1", "quote": "SVM", "attribution": "self"}],
    "relations": [rel_good],
    "alias_rules": [],
    "queries": queries[:2],
}
pipe = kg.pipeline(payload)
check("T37 pipeline端到端ok", pipe["status"] == "ok", str(pipe["status"]))
check("T38 pipeline含四问证据", all(k in pipe["evidence"]["principles"]
      for k in ["抽得准", "连得对", "对得齐", "查得到回得去"]))
check("T39 pipeline图被构建", len(pipe["result"]["graph"]["nodes"]) == 2 and len(pipe["result"]["graph"]["edges"]) == 1)

# pipeline 有坏实体时 needs_attention
payload2 = dict(payload, entities=payload["entities"] + [e_hallu])
pipe2 = kg.pipeline(payload2)
check("T40 坏实体触发needs_attention", pipe2["status"] == "needs_attention")

print("\n%d/%d 通过" % (TOTAL - len(FAILS), TOTAL))
if FAILS:
    print("失败:", FAILS)
    sys.exit(1)
print("全部通过 ✓")
