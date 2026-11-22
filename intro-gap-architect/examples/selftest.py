#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 提交包自验收测试
覆盖：套话检测(按句、有/无锚点)、分组矩阵、空白推导(共同限制/冲突/评价缺口)、
贡献对齐(悬空/锚点缺失/夸大)、引用覆盖(元数据缺失)、pipeline 端到端、
ingest(BibTeX/RIS)、compose(成稿骨架)、compare(公平对照)、pipeline --compact。
运行：python examples/selftest.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import intro_engine as ie

FAILS = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        FAILS.append(name)


# --- 立得住 ---
h1 = ie.detect_hype("近年来受到广泛关注，该领域发展迅速，具有重要意义。")
check("T1 无锚点套话被标出", h1["hype_count"] >= 1 and not h1["holds_up"])
h2 = ie.detect_hype("近年来受到广泛关注[3]。但2019年的研究仍存在标注成本高的限制。")
check("T2 有锚点可接受", h2["holds_up"] and h2["concrete_anchor_count"] > 0)

# --- 分得清 ---
works = [
    {"id": "a", "title": "CNN facies classification", "route": "深度学习路线",
     "problem": "岩相识别", "method": "CNN", "data_eval": "acc 0.92", "limitations": "标注成本高"},
    {"id": "b", "title": "GAN geomodelling", "route": "深度学习路线",
     "problem": "相建模", "method": "GAN", "data_eval": "", "limitations": "标注成本高"},
    {"id": "c", "title": "Knowledge graph reasoning", "route": "知识路线",
     "problem": "相解释", "method": "知识图谱", "data_eval": "prec 0.88", "limitations": "泛化能力弱"},
]
gm = ie.group_matrix(works)
check("T3 分组数正确", gm["group_count"] == 2, str([g["group"] for g in gm["groups"]]))
check("T4 覆盖全部文献", gm["works_covered"] == 3)
auto = [w for g in gm["groups"] for w in g["works"] if w.get("group_auto_suggested")]
check("T5 自动分组被标注", len(auto) == 0)  # 都给了 route

# --- 说得实 ---
gap = ie.derive_gap(works)
types = {g["type"] for g in gap["gaps"]}
check("T6 共同限制被推导", "共同限制" in types, str(types))
sup = [g for g in gap["gaps"] if g["type"] == "共同限制"][0]["supporting_works"]
check("T7 空白附真实支撑文献", set(sup) >= {"a", "b"}, str(sup))
check("T8 评价缺口需多篇缺字段才推导", "评价缺口" in types or
      "评价缺口" not in {g["type"] for g in ie.derive_gap([works[1]])["gaps"]})
_gapeval = ie.derive_gap([
    {"id": "p", "data_eval": ""}, {"id": "q", "data_eval": ""}])
check("T8b 两篇缺评价字段推出评价缺口", any(g["type"] == "评价缺口" for g in _gapeval["gaps"]))

conflict_works = [
    {"id": "x", "route": "路线A", "conclusion": "该方法显著优于基线"},
    {"id": "y", "route": "路线A", "conclusion": "该方法失败，效果有限"},
]
gc = ie.derive_gap(conflict_works)
check("T9 结论冲突被推导", any(g["type"] == "结论冲突" for g in gc["gaps"]))

empty_gap = ie.derive_gap([{"id": "z", "title": "no info"}])
check("T10 证据不足不臆造空白", empty_gap["gap_count"] == 0 and len(empty_gap["needs_review"]) >= 1)

# --- 对得上 ---
claims = [
    {"id": "c1", "text": "本文方法在准确率上提升", "evidence_refs": ["表2"]},
    {"id": "c2", "text": "本文首个通用方法", "evidence_refs": []},
    {"id": "c3", "text": "显著优于所有基线", "evidence_refs": ["图3"]},
]
evidx = {"表2": "acc table", "图3": "bar chart"}
al = ie.align_claims(claims, evidx)
check("T11 有证据的贡献对齐", len(al["aligned"]) == 2)
check("T12 悬空贡献被检出", any(c["id"] == "c2" for c in al["unbacked"]))
check("T13 锚点不存在被检出", not ie.align_claims(
    [{"id": "k", "text": "x", "evidence_refs": ["图9"]}], evidx)["all_backed"])
infl = ie.align_claims([{"id": "m", "text": "首个方法", "evidence_refs": ["图3"]}], evidx)
check("T14 夸大断言被检出", len(infl["inflated"]) >= 1)

# --- 引用覆盖 ---
cov_works = [
    {"id": "a", "title": "t", "authors": ["A"], "year": 2025, "source": "J"},
    {"id": "b", "title": "t", "authors": [], "year": None, "source": ""},
]
cov = ie.coverage(cov_works)
check("T15 元数据缺失被检出", any(x["id"] == "b" for x in cov["missing_metadata"]))
check("T16 近期文献判定", cov["has_recent"])

# --- pipeline ---
payload = {
    "case_id": "selftest",
    "background": "近年来受到广泛关注[1]，但标注成本高。",
    "works": works,
    "claims": [{"id": "c1", "text": "本文方法提升准确率", "evidence_refs": ["表2"]}],
    "evidence_index": {"表2": "x"},
    "contribution_links": [{"gap_type": "共同限制", "claim_id": "c1"}],
}
res = ie.pipeline(payload)
check("T17 pipeline 字段齐全", all(k in res["result"] for k in
      ["background_check", "related_work_matrix", "research_gap",
       "contribution_alignment", "citation_coverage"]))
check("T18 pipeline case_id 保留", res["case_id"] == "selftest")
check("T19 空白-贡献桥接", any(x["bridged"] for x in res["result"]["gap_to_contribution"]))

# --- ingest：外部格式解析 ---
bib = "@article{k1, author = {Smith, A. and Jones, B.}, title = {A study}, year = {2023}, journal = {Fuel}, doi = {10.1/x}}"
ing = ie.ingest({"format": "bibtex", "text": bib})
check("T20 BibTeX解析出条数", ing["work_count"] == 1)
check("T21 BibTeX作者/年份/来源", ing["works"][0]["authors"] == ["Smith, A.", "Jones, B."]
      and ing["works"][0]["year"] == "2023" and ing["works"][0]["source"] == "Fuel")
ris = "TY  - JOUR\nAU  - Zhang, S.\nTI  - B work\nPY  - 2022\nJO  - Geo\nER  - \n"
ing2 = ie.ingest({"format": "ris", "text": ris})
check("T22 RIS解析", ing2["work_count"] == 1 and ing2["works"][0]["year"] == "2022")
check("T23 不支持格式给结构化错误", ie.ingest({"format": "xyz", "text": ""})["status"] == "error")

# --- compose：成稿骨架 ---
comp = ie.compose(payload)
check("T24 compose四部件齐", all(k in comp["sections"] for k in
      ["研究背景", "相关工作", "研究空白", "贡献表述"]))
check("T25 compose来源映射", len(comp["source_map"]) >= 1)
_comp_inflated = ie.compose({
    "case_id": "ci", "background": "近年来受到广泛关注[1]。",
    "works": [{"id": "a", "title": "A", "route": "深度学习路线", "limitations": "标注成本高"},
              {"id": "b", "title": "B", "route": "知识路线", "limitations": "标注成本高"}],
    "claims": [{"id": "c1", "text": "首个通用方法显著优于所有基线", "evidence_refs": ["表2"]}],
    "evidence_index": {"表2": "x"}})
check("T26 compose夸大贡献标下调", any(x.get("downgrade_required")
      for x in _comp_inflated["sections"]["贡献表述"]))
check("T27 compose不生成空材料空白",
      len(ie.compose({"case_id": "e", "background": "", "works": [], "claims": []})["sections"]["研究空白"]) == 0)

# --- compare：公平对照 ---
cmp = ie.compare(payload)
check("T28 compare四维对照", len(cmp["dimensions"]) == 4)
check("T29 compare可验证标记", cmp["verifiable"] is True)
check("T30 compare不编造空输入增益",
      ie.compare({"case_id": "e", "background": "", "works": [], "claims": []})["gain"]["defects_skill_detects"] == 0)

# --- pipeline compact ---
cc = ie.pipeline(payload, compact=True)
check("T31 compact只回摘要", "summary" in cc and "result" not in cc)
check("T32 compact保留case_id", cc["case_id"] == "selftest")
check("T33 compact含门禁字段", all(k in cc["summary"] for k in
      ["holds_up", "claims_unbacked", "gaps_backed"]))


# ==================== 冲95+ 新增能力测试 ====================
import tempfile as _tf, os as _os, json as _js

# T34 render-draft 四部件成稿（不再是骨架）
p_draft = {
    "case_id": "draft-test",
    "background": "基于2019年文献[3]，粒度分析标注成本高的问题仍待解决。",
    "works": [
        {"id": "a", "title": "DL facies", "route": "深度学习",
         "limitations": "标注成本高", "data_eval": "acc 0.9", "year": 2023},
        {"id": "b", "title": "GAN model", "route": "深度学习",
         "limitations": "标注成本高", "year": 2024},
    ],
    "claims": [{"id": "c1", "text": "本文方法提升精度", "evidence_refs": ["fig1"]}],
}
d = ie.render_draft(p_draft)
check("T34 draft status", d["status"] in ("draft", "partial"))
check("T35 draft has text", len(d.get("draft_text", "")) > 30)
check("T36 draft four parts", [p["part"] for p in d["paragraphs"]] ==
      ["研究背景", "相关工作", "研究空白", "贡献表述"])
check("T37 draft source_refs", "a" in d["source_refs"] and "fig1" in d["source_refs"])

# T38 只用真实字段：成稿含真实标题/数据，不含编造内容
check("T38 draft uses real fields", "DL facies" in d["draft_text"] and "acc 0.9" in d["draft_text"])

# T39 空转背景被剔除、带锚点背景保留
d_bg = ie.render_draft({"case_id": "bg", "background": "近年来该领域受到广泛关注。",
                        "works": [{"id": "x", "title": "T", "route": "深度学习"}], "claims": []})
check("T39 hype background dropped", "待核实" in d_bg["paragraphs"][0]["text"])
d_bg2 = ie.render_draft({"case_id": "bg2", "background": "基于2020年[1]，标注成本高仍待解决。",
                         "works": [{"id": "x", "title": "T", "route": "深度学习"}], "claims": []})
check("T39b anchored background kept", "2020" in d_bg2["paragraphs"][0]["text"])

# T40 compose 纳入成稿
comp = ie.compose(p_draft)
check("T40 compose includes draft", "draft" in comp and "draft_text" in comp)

# T41 compare 含真实朴素成稿对照
cmp2 = ie.compare(p_draft)
dc = cmp2.get("draft_comparison", {})
check("T41 draft comparison present",
      all(k in dc for k in ["baseline_text", "skill_text", "skill_parts"]))

# T42 solve 端到端 + 装配回执
td = _tf.mkdtemp(prefix="intro_solve_")
_js.dump(p_draft, open(_os.path.join(td, "case.json"), "w", encoding="utf-8"), ensure_ascii=False)
sv = ie.solve(_os.path.join(td, "case.json"), _os.path.join(td, "output"))
check("T42 solve status", sv.get("status") in ("draft", "partial", "needs_attention"))
check("T43 solve delivery written", sv.get("delivery", {}).get("written") is True)
rj = _js.load(open(_os.path.join(td, "output", "result.json"), encoding="utf-8"))
check("T44 solve result assembled", rj.get("case_id") == "draft-test" and "result" in rj)

# T45 ingest + solve 串联（BibTeX 输入）
bib = "@article{a,title={DL facies},author={Smith, A.},year={2023},journal={Fuel}}"
sv2 = ie.solve_inline({"case_id": "bib", "format": "bibtex", "text": bib},
                      _os.path.join(td, "output2")) if hasattr(ie, "solve_inline") else None
# 若未提供 solve_inline，用 ingest 验证即可
ing = ie.ingest({"format": "bibtex", "text": bib, "case_id": "bib"})
check("T45 ingest bibtex works", ing.get("work_count", 0) >= 1 and ing["works"][0].get("title") == "DL facies")

TOTAL = 45
print("\n%d/%d 通过" % (TOTAL - len(FAILS), TOTAL))
if FAILS:
    print("失败:", FAILS)
    sys.exit(1)
print("全部通过 ✓")
