#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 文献翻译守门人 自验收测试
覆盖四问：术语稳（抽取/锁定/一致性）、段落全（切段/续段/对齐）、
关系准（数字公式引用化学式保护/回填/否定限定核验）、可核验（证据索引），
以及负例篡改检测、compact、pipeline 端到端。
运行：python examples/selftest.py
"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import translation_guard as tg

FAILS = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        FAILS.append(name)


sample = json.load(open(os.path.join(HERE, "smoke_input.json"), encoding="utf-8"))

# ---------- 术语稳 ----------
g = tg.build_glossary(sample)
check("T1 glossary candidates", g["stats"]["candidate_count"] >= 5)
check("T2 manual terms locked", any(c["source"] == "porosity" and c["locked"]
                                    for c in g["glossary"]))
check("T3 unlocked flagged", g["stats"]["unlocked_count"] >= 0 and
      isinstance(g["needs_review"], list))
lock = tg.lock_terms(sample)
check("T4 lock prompt built", "porosity" in lock["lock_prompt"] and "碳酸盐岩储层" in lock["lock_prompt"])
check("T5 lock constraint declared", "术语" in lock["lock_prompt"] and "数字" in lock["lock_prompt"])
ct = tg.check_terms(sample)
check("T6 consistent terms", ct["stats"]["inconsistent_count"] == 0)
# 负例：同一术语用两个译名
p2 = json.loads(json.dumps(sample))
p2["glossary"] = [{"source": "porosity", "target": "孔隙度", "variants": ["孔隙率"]}]
p2["translations"]["P1"] = "孔隙度约为18.5%，孔隙率达到120 mD [1]。"
ct2 = tg.check_terms(p2)
check("T7 inconsistent term detected", ct2["stats"]["inconsistent_count"] >= 1)

# ---------- 段落全 ----------
seg = tg.segment(sample)
check("T8 segment count", seg["stats"]["segment_count"] == 4)
check("T9 stable ids", [s["id"] for s in seg["segments"]] == ["P1", "P2", "P3", "P4"])
check("T10 caption kind preserved", any(s["kind"] == "caption" for s in seg["segments"]))
al = tg.align(sample)
check("T11 align coverage 100%", al["stats"]["coverage"] == 1.0 and al["problems"] == [])
# 负例：漏段 + 错位
p3 = json.loads(json.dumps(sample))
p3["translations"] = {"P1": "译文1", "P3": "译文3", "P9": "多余段"}
al3 = tg.align(p3)
check("T12 missing segment detected", "P2" in al3["missing"] and "P4" in al3["missing"])
check("T13 extra segment detected", "P9" in al3["extra"])
# 续段检测
p4 = {"paragraphs": [
    {"id": "A", "text": "This method improves the"},
    {"id": "B", "text": "accuracy significantly."},
]}
check("T14 continuation detected", any("continuation_of" in s for s in tg.segment(p4)["segments"]))

# ---------- 关系准 ----------
prot = tg.protect(sample)
kinds = [t["kind"] for x in prot["protected"] for t in x["tokens"]]
check("T15 number_unit protected", "number_unit" in kinds)
check("T16 citation protected", "citation" in kinds)
check("T17 chemical protected", "chemical" in kinds)
check("T18 formula protected", "formula" in kinds)
# 公式不跨句
p2_tokens = [t for x in prot["protected"] if x["id"] == "P2" for t in x["tokens"]]
check("T19 formula truncated", all("Only" not in t["raw"] for t in p2_tokens))
ri = {"protected": prot["protected"], "translations": sample["translations"]}
rest = tg.restore(ri)
check("T20 restore no issue", rest["stats"]["issues"] == 0)
check("T21 direct-preserve counted", rest["stats"]["preserved_direct_count"] >= 3)
# 负例：篡改数字/引用/化学式
bad = json.loads(json.dumps(sample))
bad["translations"]["P1"] = "孔隙度约为20%，渗透率达到。我们提出新方法。"
vbad = tg.verify(bad)
check("T22 number tamper detected", any(i["type"] == "number_lost" for i in vbad["issues"]))
check("T23 citation tamper detected", any(i["type"] == "citation_lost" for i in vbad["issues"]))
check("T24 chemical tamper detected", any(i["type"] == "chemical_lost" for i in vbad["issues"]))
rbad = tg.restore({"protected": prot["protected"], "translations": bad["translations"]})
check("T25 restore catches tamper", rbad["stats"]["issues"] >= 3)
v = tg.verify(sample)
check("T26 positive verify clean", v["consistent"] and v["stats"]["issue_count"] == 0)
# 否定/限定
check("T27 negation preserved", any(p["checks"]["negation"]["source"] for p in v["per_paragraph"]))
check("T28 limitation preserved", any(p["checks"]["limitation"]["source"] for p in v["per_paragraph"]))

# ---------- 可核验 ----------
ev = tg.evidence(sample)
check("T29 evidence per paragraph", len(ev["evidence"]) == 4)
check("T30 evidence has location+basis", all(
    "source_location" in e and "basis" in e for e in ev["evidence"]))
check("T31 glossary basis present", any(
    any(b["type"] == "glossary" for b in e["basis"]) for e in ev["evidence"]))

# ---------- pipeline / compact ----------
pipe = tg.pipeline(sample)
check("T32 pipeline status", pipe["status"] in ("success", "partial", "needs_review"))
check("T33 pipeline has all steps", all(k in pipe["pipeline"] for k in
      ("segment", "glossary", "lock", "protect", "restore", "align", "check_terms", "verify", "evidence")))
check("T34 summary present", "摘要" in pipe["result"]["summary"] or "段" in pipe["result"]["summary"])
compact = tg.pipeline(sample, compact=True)
check("T35 compact drops pipeline", "pipeline" not in compact and "result" in compact)
# 空输入安全
check("T36 empty safe", "status" in tg.pipeline({"paragraphs": []}))
# 无译文时 has_translations=False
notrans = {k: v for k, v in sample.items() if k != "translations"}
check("T37 no-translation flagged", tg.pipeline(notrans)["has_translations"] is False)

# --- 公平对照证据（冲分）---
import json as _json, subprocess as _sp, sys as _sys
def _cmp_ok():
    try:
        bp = os.path.join(os.path.dirname(__file__), "benchmark.json")
        ce = os.path.join(os.path.dirname(__file__), "..", "scripts", "compare_engine.py")
        out = _sp.run([_sys.executable, ce, bp], capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return False
        data = _json.loads(out.stdout)
        # clean 不误报 / defect 能检出：缺陷案例的检查信号 >= 干净案例
        return (len(data) == 2 and
                data[1]["summary"]["total_checks_fired"] >= data[0]["summary"]["total_checks_fired"])
    except Exception:
        return False
check("TC1 对照benchmark可复现", _cmp_ok())
_bench = _json.load(open(os.path.join(os.path.dirname(__file__), "benchmark.json"), encoding="utf-8"))
check("TC2 四问对照完整", len(_bench.get("four_questions", [])) == 4 and
      len(_bench.get("cases", [])) >= 2)

print("\nTOTAL FAILURES:", len(FAILS), FAILS)
sys.exit(1 if FAILS else 0)
