#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 学术语言润色守门/完成器 自验收测试
覆盖四问（改得对/说得像/没改坏/讲得清）+ 完成器 D/A/S/TC 系列。
运行：python examples/selftest.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import polish_engine as pe

FAILS = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        FAILS.append(name)


sample = json.load(open(os.path.join(HERE, "smoke_input.json"), encoding="utf-8"))

# ---------- 逐句 / 守护 ----------
seg = pe.segment(sample)
check("G1 segment count", seg["stats"]["sentence_count"] >= 4)
check("G2 stable ids", all(s["id"].startswith("P") and "_S" in s["id"] for s in seg["sentences"]))
prot = pe.protect(sample)
kinds = [t["kind"] for x in prot["protected"] for t in x["tokens"]]
check("G3 citation protected", "citation" in kinds)
check("G4 refmark protected", "refmark" in kinds)
check("G5 chemical protected", "chemical" in kinds)
check("G6 formula protected", "formula" in kinds)
check("G7 limit protected", "limit" in kinds)
check("G8 no naked number eating citation",
      any(t["text"] == "[1]" for x in prot["protected"] for t in x["tokens"]))

# ---------- 改得对 ----------
gram = pe.detect_grammar(sample)
gtypes = gram["stats"]["by_type"]
check("C1 repeated word detected", gtypes.get("repeated_word", 0) >= 1)
check("C2 double article detected", gtypes.get("double_article", 0) >= 1)
check("C3 has reason", all(i.get("reason") for i in gram["issues"]))

# ---------- 说得像 ----------
terms = pe.check_terms(sample)
check("R1 glossary counted", terms["glossary_terms"] == 3)
# 负例：同一 source 两个 target
p2 = json.loads(json.dumps(sample))
p2["glossary"] = [{"source": "porosity", "target": "孔隙度"},
                  {"source": "Porosity", "target": "孔隙率"}]
check("R2 source multi target detected", pe.check_terms(p2)["stats"]["inconsistent_count"] >= 1)
reg = pe.check_register(sample)
check("R3 register target", reg["target_register"] == "journal")
# 负例：绝对化 + 口语化
p3 = json.loads(json.dumps(sample))
p3["paragraphs"] = [{"id": "P1", "text": "This a lot of method definitely proves the results."}]
check("R4 absolutist detected", len(pe.check_register(p3)["hits"]["absolutist"]) >= 1)
check("R5 colloquial detected", len(pe.check_register(p3)["hits"]["colloquial"]) >= 1)

# ---------- 没改坏 ----------
pres = pe.check_preserve(sample)
check("P1 preserve checked", pres["checked"] is True)
check("P2 numbers intact", pres["counts"]["protected_lost"] == 0 and pres["counts"]["protected_added"] == 0)
# 负例1：删掉 approximately（弱化词丢失）+ 换掉 [1]
p4 = json.loads(json.dumps(sample))
p4["polished"] = {"P1": "The porosity is 18.5% [2], and the permeability reaches 120 mD (Fig. 2). "
                       "We propose a method for CO2 flooding that significantly improves recovery.",
                  "P2": sample["polished"]["P2"]}
pres4 = pe.check_preserve(p4)
check("P3 hedge weakened detected", pres4["counts"]["hedge_weakened"] >= 1)
check("P4 citation changed detected", pres4["counts"]["protected_lost"] >= 1 or pres4["counts"]["protected_added"] >= 1)
# 负例2：新增绝对化词
p5 = json.loads(json.dumps(sample))
p5["polished"] = {"P1": sample["polished"]["P1"].replace("not always", "").replace("propose", "definitely prove"),
                  "P2": sample["polished"]["P2"]}
check("P5 claim strengthened detected", pe.check_preserve(p5)["counts"]["claim_strengthened"] >= 1)
# 负例3：否定词丢失
p6 = json.loads(json.dumps(sample))
p6["polished"] = {"P1": sample["polished"]["P1"].replace("not always homogeneous", "always homogeneous"),
                  "P2": sample["polished"]["P2"]}
check("P6 negation lost detected", pe.check_preserve(p6)["counts"]["negation_lost"] >= 1)

# ---------- 讲得清 / 成稿 ----------
dr = pe.render_draft(sample)
check("D1 draft status", dr["status"] in ("draft", "partial"))
check("D2 blocks have source+target", all("source" in b and "target" in b for b in dr["blocks"]))
check("D3 polished block present", any(b["status"] == "polished" for b in dr["blocks"]))
check("D4 reasons present", sum(len(b["reasons"]) for b in dr["blocks"]) >= 1)
check("D5 source refs", len(dr["source_refs"]) == len(dr["blocks"]))
check("D6 polished text built", "原文:" in dr["polished_text"] and "改文:" in dr["polished_text"])
pl = pe.pipeline(sample, with_draft=True)
check("D7 pipeline draft detail", "draft_detail" in pl["result"])
check("D8 pipeline polished", bool(pl["result"].get("polished_draft")))

# ---------- A：真实输入适配 ----------
tmp = tempfile.mkdtemp(prefix="polish_st_")
src = os.path.join(tmp, "manuscript.txt")
open(src, "w", encoding="utf-8").write("The result is approximately 18.5% [1].\nCO2 was measured.")
gfile = os.path.join(tmp, "terms.json")
json.dump({"glossary": [{"source": "CO2", "target": "二氧化碳"}]}, open(gfile, "w", encoding="utf-8"))
ap = pe._adapt_case({"source_files": [src], "glossary_file": gfile}, tmp)
check("A1 source file adapted", len(pe._paragraphs(ap)) == 2)
check("A2 glossary file adapted", any(g.get("source") == "CO2" for g in ap.get("glossary", [])))
check("A3 adapter notes", isinstance(ap.get("adapter_notes"), list))
# 缺译文不臆造
ad = pe.render_draft(ap)
check("A4 no polished -> pending", len(ad["pending_polish"]) >= 1)
check("A5 no fabrication", all("〔待润色" in b["target"] for b in ad["blocks"]))

# ---------- S：solve 端到端 ----------
case = os.path.join(tmp, "case.json")
json.dump({"case_id": "e2e-demo", "source_text": "The porosity is approximately 18.5% [1].\nNo difference was observed."},
          open(case, "w", encoding="utf-8"))
out = os.path.join(tmp, "out")
sv = pe.solve(case, out)
check("S1 delivery written", sv["delivery"]["written"] is True and sv["delivery"]["bytes"] > 0)
check("S2 result.json exists", os.path.exists(os.path.join(out, "result.json")))
saved = json.load(open(os.path.join(out, "result.json"), encoding="utf-8"))
check("S3 saved case_id", saved.get("case_id") == "e2e-demo")
check("S4 saved has draft_text", isinstance(saved.get("result", {}).get("draft_text"), str))
check("S5 saved has evidence", isinstance(saved.get("result", {}).get("evidence_index"), list))
check("S6 source count", sv.get("source_count") == 2)

# ---------- TC：诚实降级 ----------
tc = pe.solve(os.path.join(tmp, "case.json"), out)  # 正常路径对照
empty = os.path.join(tmp, "empty.json")
json.dump({"case_id": "empty"}, open(empty, "w", encoding="utf-8"))
sv2 = pe.solve(empty, os.path.join(tmp, "out2"))
check("TC1 empty input honest", sv2["status"] == "needs_review")
check("TC2 empty still delivers", sv2["delivery"]["written"] is True)
check("TC3 no fabrication on empty", "无法成稿" in sv2["result"]["summary"])
# 无 polished 不做守恒核验（不臆造）
np = pe.pipeline(ap)
check("TC4 preserve not checked without polished", np["result"]["preservation"]["checked"] is False)
check("TC5 honest needs_review", any("无真实" in n for n in np["result"]["verification"]["needs_review"]))

print("\nTOTAL FAILURES:", len(FAILS), FAILS)
sys.exit(1 if FAILS else 0)
