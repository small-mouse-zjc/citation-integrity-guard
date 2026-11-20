#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 提交包自验收测试
覆盖四个去重判据、版本歧义、编号展开、双向一致性核验、
字段缺失标注与 pipeline 端到端，共 14 项断言。
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
     "authors": ["Smith, A."], "year": 2021, "doi": "10.1/abc"}

# 去重判据
b1 = dict(a); b1["doi"] = "https://doi.org/10.1/abc"
check("T1 doi_exact", ce._dedup_decision(a, b1)[2] == "doi_exact")
b2 = dict(a); b2["doi"] = ""
check("T2 title_year_exact", ce._dedup_decision(a, b2)[2] == "title_year_exact")
b3 = dict(a); b3["doi"] = ""; b3["title"] = "Machine Learning for CO2 Phase Behaviours"
check("T3 fuzzy_title_author_year", ce._dedup_decision(a, b3)[2] == "fuzzy_title_author_year")
c = {"title": "A totally different study", "authors": ["Jones, B."], "year": 2019}
check("T4 no_match", not ce._dedup_decision(a, c)[0])
v = {"title": "Machine Learning for CO2 Phase Behavior (preprint)",
     "authors": ["Smith, A."], "year": 2020, "doi": "10.2/xyz"}
check("T5 version_variant not merged", not ce._dedup_decision(a, v)[0]
      and ce._dedup_decision(a, v)[2] == "version_variant")

# 编号展开与核验
check("T6 expand range", ce._expand_citation("1,3-5") == [1, 3, 4, 5])
ents = [{"id": "a", "new_number": 1}, {"id": "b", "new_number": 2}]
check("T7 verify consistent", ce.verify("text [1] and [2]", ents)["consistent"])
check("T8 dangling detected", 3 in ce.verify("text [1] and [3]", ents)["dangling_citations"])
check("T9 uncited detected", 2 in ce.verify("text [1]", ents)["uncited_entries"])
check("T10 duplicate detected",
      1 in ce.verify("text [1]", [{"id": "a", "new_number": 1},
                                  {"id": "b", "new_number": 1}])["duplicate_numbers"])

# 字段缺失标注
out = ce.normalize([{"title": "only title"}])
check("T11 missing fields issue", any(i["type"] == "missing_fields" for i in out["issues"]))

# 端到端
r = ce.pipeline({"case_id": "e2e", "entries": [a, b1, c],
                 "manuscript": "Works [1] and [2]. More [3]."})
check("T12 case_id preserved", r["case_id"] == "e2e")
check("T13 merged count", r["pipeline"]["normalize"]["stats"]["merged_count"] == 1)
check("T14 bibliography length", len(r["result"]["bibliography"]) == 2)

print("\nTOTAL FAILURES:", len(FAILS), FAILS)
sys.exit(1 if FAILS else 0)
