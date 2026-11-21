#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 提交包自验收测试
覆盖：四档去重判据、版本歧义、编号展开、双向一致性、首次出现顺序、
字段缺失标注、可编辑正文改写、BibTeX/RIS/CNKI 解析、引用落点定位、
论断核验预筛、修复前后对照、APA 规范扩展、紧凑摘要与 pipeline 端到端。
运行：python examples/selftest.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import citation_engine as ce

FAILS = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        FAILS.append(name)


a = {"title": "Machine Learning for CO2 Phase Behavior",
     "authors": ["Smith, A."], "year": 2021, "doi": "10.1/abc", "id": "smith2021"}

# ---------- 去重判据（T1-T5）----------
b1 = dict(a); b1["doi"] = "https://doi.org/10.1/abc"
check("T1 doi_exact", ce._dedup_decision(a, b1)[2] == "doi_exact")
b2 = dict(a); b2["doi"] = ""
check("T2 title_year_exact", ce._dedup_decision(a, b2)[2] == "title_year_exact")
b3 = dict(a); b3["doi"] = ""; b3["title"] = "Machine Learning for CO2 Phase Behaviours"
check("T3 fuzzy_title_author_year", ce._dedup_decision(a, b3)[2] == "fuzzy_title_author_year")
c = {"title": "A totally different study", "authors": ["Jones, B."], "year": 2019, "id": "jones2019"}
check("T4 no_match", not ce._dedup_decision(a, c)[0])
v = {"title": "Machine Learning for CO2 Phase Behavior (preprint)",
     "authors": ["Smith, A."], "year": 2020, "doi": "10.2/xyz"}
check("T5 version_variant not merged", not ce._dedup_decision(a, v)[0]
      and ce._dedup_decision(a, v)[2] == "version_variant")

# ---------- 编号与一致性（T6-T11）----------
check("T6 expand range", ce._expand_citation("1,3-5") == [1, 3, 4, 5])
ents = [{"id": "a", "new_number": 1}, {"id": "b", "new_number": 2}]
check("T7 verify consistent", ce.verify("text [1] and [2]", ents)["consistent"])
check("T8 dangling detected", 3 in ce.verify("text [1] and [3]", ents)["dangling_citations"])
check("T9 uncited detected", 2 in ce.verify("text [1]", ents)["uncited_entries"])
check("T10 duplicate detected",
      1 in ce.verify("text [1]", [{"id": "a", "new_number": 1},
                                  {"id": "b", "new_number": 1}])["duplicate_numbers"])
out = ce.normalize([{"title": "only title"}])
check("T11 missing fields issue", any(i["type"] == "missing_fields" for i in out["issues"]))
# version_variant（预印本vs正式版）虽不合并，但必须进入 needs_review 而非静默丢弃
nv = ce.normalize([a, dict(v, id="v")])
check("T11b version variant to review",
      nv["stats"]["needs_review_count"] >= 1 and nv["status"] == "needs_review")

# ---------- 可编辑正文改写（T12-T13）----------
ren_e = [{"id": "x", "old_number": 1}, {"id": "y", "old_number": 2}]
rr = ce.renumber("First [1]. Then [1,2].", ren_e)
check("T12 rewrite changes numbers", "[1]" in rr["rewritten_manuscript"]
      and rr["mapping"]["x"] == 1 and rr["mapping"]["y"] == 2)
check("T13 rewrite records changes", isinstance(rr.get("rewrite_changes"), list))
# 首次出现顺序倒置 → 重排后 y 应为 1
rr2 = ce.renumber("Cite [2] first, then [1].", ren_e)
check("T13b first-appearance order", rr2["mapping"]["y"] == 1 and rr2["mapping"]["x"] == 2)

# ---------- 首次出现顺序校验（T14）----------
ov = ce.verify("text [2] then [1]", [{"id": "y", "new_number": 1}, {"id": "x", "new_number": 2}])
check("T14 order violation flagged", len(ov["order_violations"]) >= 1)

# ---------- ingest 三格式（T15-T18）----------
bib = """@article{li2020,
  title = {Carbon storage in deep saline aquifers},
  author = {Li, H. and Wang, J. and Zhang, S.},
  journal = {Fuel}, year = {2020}, volume = {281}, pages = {118-126},
  doi = {10.1016/j.fuel.2020.118126}
}"""
ib = ce.ingest(bib, "bibtex")
check("T15 bibtex parse", ib["detected_format"] == "bibtex" and ib["stats"]["parsed_count"] == 1
      and len(ib["entries"][0]["authors"]) == 3)
ris = """TY  - JOUR
AU  - Smith, A.
TI  - A ris sample title
PY  - 2019/05
JO  - Geochimica
SP  - 10
EP  - 20
DO  - 10.1/ris
ER  - 
"""
ir = ce.ingest(ris, "ris")
check("T16 ris parse", ir["stats"]["parsed_count"] == 1 and ir["entries"][0]["pages"] == "10-20")
cnki = "题名: 沉积学中的人工智能\n作者: 张三, 李四\n来源: 沉积学报\n年份: 2022\n\n题名: CO2封存进展\n作者: 王五\n来源: 岩性油气藏\n年份: 2021"
ic = ce.ingest(cnki, "cnki")
check("T17 cnki parse", ic["stats"]["parsed_count"] == 2 and ic["entries"][0]["authors"][0] == "张三")
check("T18 ingest auto-detect", ce.ingest(bib, "auto")["detected_format"] == "bibtex")

# ---------- 引用落点定位（T19-T20）----------
ms = "采样点位于鄂尔多斯盆地。实验测得孔隙度为18.5%，渗透率显著提高（Zhang等, 2020）。本文提出一种新方法。"
ents_z = [{"id": "zhang2020", "title": "Porosity and permeability of sandstone reservoirs"}]
pl = ce.place_citations(ms, ents_z)
check("T19 place detects gaps", pl["stats"]["citation_gaps"] >= 1)
check("T19b place numeric signal", any(s["has_numeric"] for s in pl["sentences"]))
ms2 = "该方法准确率达到0.92 [1]。结果见表1。"
pl2 = ce.place_citations(ms2, ents_z)
check("T20 covered not gap", all(not (s["needs_citation"] and not s["has_citation"])
                                 for s in pl2["sentences"]))

# ---------- 论断核验预筛（T21-T23）----------
bad = {"id": "bad1", "title": "X", "authors": [], "year": 1650, "doi": "badformat", "id": "bad1"}
cl = ce.check_claims("方法准确率达到0.92 [@bad1]。", [bad])
check("T21 metadata anomalies", cl["stats"]["metadata_anomaly_count"] >= 3)
good = {"id": "g1", "title": "Deep learning for CO2 phase behavior prediction",
        "authors": ["Smith, A."], "year": 2021, "journal": "Fuel", "doi": "10.1/g"}
cl2 = ce.check_claims("本文用深度学习预测CO2相行为 [@g1]。", [good], low=0.05, high=0.2)
check("T22 plausible not suspicious", 0 not in cl2["suspicious_claims"])
cl3 = ce.check_claims("量子纠缠调控了细胞凋亡 [@g1]。", [good], low=0.05, high=0.2)
check("T23 topic mismatch suspected", 0 in cl3["suspicious_claims"])

# ---------- compare 前后对照（T24）----------
before = {"manuscript": "text [3] and [1]", "entries": [
    {"id": "a", "new_number": 1}, {"id": "b", "new_number": 2}]}
after = {"manuscript": "text [1] and [2]", "entries": [
    {"id": "a", "new_number": 1}, {"id": "b", "new_number": 2}]}
cmp = ce.compare(before, after)
check("T24 compare improved", cmp["summary"]["improved_metrics"] >= 1
      and cmp["summary"]["consistent_after"] is True)

# ---------- APA 规范扩展（T25）----------
apa = ce.format_entry_apa({"authors": ["Smith, A.", "Li, H."], "year": 2021,
                           "title": "A study", "type": "article",
                           "journal": "Fuel", "volume": "281", "pages": "1-9",
                           "doi": "10.1/a"})
check("T25 apa format", "Smith, A." in apa and "& Li, H." in apa and "https://doi.org/" in apa)

# ---------- pipeline 端到端 + compact（T26-T29）----------
entries = [a, dict(a, id="a2", doi=""), c]
pipe = ce.pipeline({"case_id": "e2e", "entries": entries,
                    "manuscript": "Works [1] and [2]. More [3]."})
check("T26 case_id preserved", pipe["case_id"] == "e2e")
check("T27 merged count", pipe["pipeline"]["normalize"]["stats"]["merged_count"] == 1)
check("T28 bibliography length", len(pipe["result"]["bibliography"]) == 2)
check("T28b new capabilities present", "citation_placement" in pipe["result"]
      and "claim_check" in pipe["result"] and "summary" in pipe["result"])
compact = ce.pipeline({"case_id": "e2e", "entries": entries,
                       "manuscript": "Works [1] and [2]. More [3]."}, compact=True)
check("T29 compact slimmer", "pipeline" not in compact and "summary" in compact["result"])

print("\nTOTAL FAILURES:", len(FAILS), FAILS)
sys.exit(1 if FAILS else 0)
