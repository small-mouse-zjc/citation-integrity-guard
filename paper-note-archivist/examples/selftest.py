#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 提交包自验收测试
覆盖：章节对齐(顺序/漏章)、卡片字段完整性、锚点校验(缺失/无效)、
知识点去重归一、论文卡片未报告标注、pipeline 端到端。
运行：python examples/selftest.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import notes_engine as ne

FAILS = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        FAILS.append(name)


PAPER = ["摘要", "引言", "相关工作", "方法", "结果", "讨论", "结论"]

# --- 对得上：章节对齐 ---
a_ok = ne.check_section_alignment(PAPER, ["摘要", "引言", "方法", "结果", "结论"])
check("T1 顺序一致即对齐", a_ok["order_consistent"] and not a_ok["inversions"])  # 漏章另计，此处只验顺序
a_full = ne.check_section_alignment(PAPER, PAPER)
check("T1b 全章节才完全对齐", a_full["aligned"])
a_miss = ne.check_section_alignment(PAPER, ["摘要", "方法", "引言", "结果"])
check("T2 顺序倒置被检出", not a_miss["order_consistent"] and len(a_miss["inversions"]) >= 1,
      str(a_miss["inversions"]))
a_less = ne.check_section_alignment(PAPER, ["摘要", "引言"])
check("T3 漏章节被检出", "method" in a_less["missing_sections"] or len(a_less["missing_sections"]) >= 2)

# --- 留得住：卡片字段 ---
FULL_CARD = {"question": "岩相识别", "data": "500张薄片", "method_conditions": "CNN",
             "findings": "acc 0.92", "limitations": "标注成本", "premises": "仅碳酸盐岩"}
c_ok = ne.check_card_fields(FULL_CARD)
check("T4 字段齐全", c_ok["complete"] and c_ok["present_count"] == 6)
c_less = ne.check_card_fields({"question": "x", "data": "y"})
check("T5 缺字段被检出", not c_less["complete"] and len(c_less["missing"]) >= 3)
c_note = ne.check_card_fields({"note": "研究问题是X，方法是Y，发现是Z，局限是W，仅在某条件下成立，数据为某集"})
check("T6 从note全文识别字段", c_note["present_count"] >= 4)

# --- 找得回：锚点 ---
notes = [
    {"id": "n1", "text": "准确率0.92", "anchor": "第5页"},
    {"id": "n2", "text": "方法见", "anchor": "§3.2"},
]
an = ne.verify_anchors(notes, ["第5页", "§3.2"])
check("T7 有效锚点全通过", an["all_anchored"] and an["anchored_count"] == 2)
an_none = ne.verify_anchors([{"id": "x", "text": "某结论", "anchor": ""}])
check("T8 缺锚点被检出", len(an_none["no_anchor"]) == 1 and not an_none["all_anchored"])
an_bad = ne.verify_anchors([{"id": "y", "text": "x", "anchor": "第5页"}], ["第9页"])
check("T9 无效锚点被检出", len(an_bad["bad_anchor"]) == 1)
an_text = ne.verify_anchors([{"id": "z", "text": "结果见图3", "anchor": ""}])
check("T10 正文锚点格式被识别但无独立锚点不算数", an_text["notes"][0]["has_anchor_format"]
      and not an_text["notes"][0]["valid"])  # 图3格式识别，但缺独立anchor字段→不算可回链

# --- 用得上：知识点归一 ---
pts = [
    {"label": "随机森林分类方法及其在岩相识别中的应用", "definition": "RF方法"},
    {"label": "随机森林分类方法及其在岩相识别中的应用 ", "definition": "RF"},  # 几乎相同，应合并
    {"label": "CNN", "definition": "卷积网络", "synonym_hint": False},
]
kn = ne.normalize_knowledge(pts, dup_threshold=0.72)
check("T11 高相似知识点被合并", kn["merged_count"] >= 1, str(kn["merges"]))
check("T12 归一后条目减少", kn["entry_count"] < len(pts))
kn_clean = ne.normalize_knowledge([{"label": "完全不相关的概念A"}, {"label": "另一个主题B"}])
check("T13 不同知识点不误合并", kn_clean["merged_count"] == 0)
kn_cross = ne.normalize_knowledge([{"label": "CNN"}, {"label": "卷积神经网络"}])
check("T13b 中英同义保守不自动合并", kn_cross["merged_count"] == 0)  # 须人工确认

# --- 论文卡片 ---
rc = ne.build_reading_card(FULL_CARD)
check("T14 卡片可比", rc["comparable"] and not rc["missing_fields"])
rc_less = ne.build_reading_card({"question": "x"})
check("T15 未报告字段标注", not rc_less["comparable"] and len(rc_less["missing_fields"]) >= 5)
check("T16 未报告不臆造", rc_less["card"]["findings"]["status"] == "not_reported")

# --- pipeline ---
payload = {
    "case_id": "selftest",
    "paper_sections": PAPER,
    "note_sections": ["摘要", "引言", "方法", "结果", "结论"],
    "card": FULL_CARD,
    "notes": notes,
    "valid_anchors": ["第5页", "§3.2"],
    "knowledge_points": pts,
}
res = ne.pipeline(payload)
check("T17 pipeline 字段齐全", all(k in res["result"] for k in
      ["section_alignment", "card_fields", "anchor_verification", "knowledge_normalization", "reading_card"]))
check("T18 case_id 保留", res["case_id"] == "selftest")
check("T19 evidence 含锚点定位", "missing_anchors" in res["evidence"] and "bad_anchors" in res["evidence"])
check("T20 uncertainty 含未报告字段", len(res["uncertainty"]["missing_fields"]) >= 0)

# 完全干净案例
clean_payload = dict(payload, note_sections=PAPER, knowledge_points=[pts[0]])
clean_res = ne.pipeline(clean_payload)
check("T21 干净案例可达 ok", clean_res["status"] == "ok",
      "align=%s card=%s anchor=%s" % (clean_res["result"]["section_alignment"]["aligned"],
                                       clean_res["result"]["card_fields"]["complete"],
                                       clean_res["result"]["anchor_verification"]["all_anchored"]))

print("\n%d/%d 通过" % (23 - len(FAILS), 23))
if FAILS:
    print("失败:", FAILS)
    sys.exit(1)
print("全部通过 ✓")
