#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""examples/selftest.py — 02 题自验收"""
import os
import sys
import tempfile
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import polish_audit as pa  # noqa: E402
import office_io as oi  # noqa: E402
import validate_result as vr  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        FAILS.append(name)


SRC = """# Abstract
Recent studies suggest that the method may improve accuracy by 12.5% on the benchmark [1,2]. However, this improvement was not observed in the low-data regime, and the result cannot be generalized without further validation.

# Methods
We analyzed 48 samples with a 7:3 split. The porosity was measured at 20 MPa.
"""

CLEAN = """# Abstract
Recent studies suggest that the method may improve accuracy by 12.5% on the benchmark [1,2]. However, this improvement was not observed in the low-data regime, and the result cannot be generalized without further validation.

# Methods
We analyzed 48 samples with a 7:3 split. The porosity was measured at 20 MPa.
"""

BAD_NUM = CLEAN.replace("12.5%", "15%")
BAD_CITE = CLEAN.replace("[1,2]", "")
BAD_HEDGE = CLEAN.replace("may improve", "improves")
BAD_BOOST = CLEAN.replace("suggest", "demonstrate")
BAD_NEG = CLEAN.replace("was not observed", "was observed")
BAD_PARA = """# Abstract
Recent studies suggest that the method may improve accuracy by 12.5% on the benchmark [1,2].
"""

TB = [{"source": "porosity", "target": "孔隙度", "forbidden": "孔隙率"}]

r = pa.audit(SRC, CLEAN)
check("T1 干净改文 gate=pass", r["gate"] == "pass", r["gate"])
check("T2 干净改文无 critical", r["counts"]["critical"] == 0)
check("T3 数字被改检出", pa.audit(SRC, BAD_NUM)["gate"] == "fail"
      and any(v["type"] == "number_missing" for v in pa.audit(SRC, BAD_NUM)["violations"]))
check("T4 引用丢失检出", any(v["type"] == "citation_missing" for v in pa.audit(SRC, BAD_CITE)["violations"]))
check("T5 限定丢失检出", any(v["type"] == "hedge_dropped" for v in pa.audit(SRC, BAD_HEDGE)["violations"]))
check("T6 强断言新增检出", any(v["type"] == "booster_added" for v in pa.audit(SRC, BAD_BOOST)["violations"]))
check("T7 否定丢失检出", any(v["type"] == "negation_dropped" for v in pa.audit(SRC, BAD_NEG)["violations"]))
check("T8 段落丢失检出", any(v["type"] == "paragraph_dropped" for v in pa.audit(SRC, BAD_PARA)["violations"]))
check("T9 术语禁用变体检出", any(v["type"] == "term_forbidden"
                               for v in pa.audit("The porosity is high.", "The 孔隙率 is high.", TB)["violations"]))
check("T10 术语目标缺失检出", any(v["type"] == "term_missing"
                               for v in pa.audit("The porosity is high.", "The permeability is high.", TB)["violations"]))
check("T11 ledger 数字计数", len(pa.ledger(SRC)["numbers"]) >= 5)
check("T12 ledger 引用存在", "[1,2]" in pa.ledger(SRC)["citations"])

td = tempfile.mkdtemp(prefix="polish_test_")
docx = os.path.join(td, "a.docx")
oi.write_docx(docx, ["第一段 text", "第二段 line"], "Title")
check("T13 docx 写出", os.path.exists(docx) and os.path.getsize(docx) > 0)
got = oi.docx_paragraphs(docx)
check("T14 docx 读回内容", any("第一段" in x for x in got) and any("第二段" in x for x in got), str(got))

res = {
    "case_id": "selftest",
    "status": "success",
    "result": {
        "polished_text": CLEAN,
        "paragraphs": [{"id": "P1", "source_ref": "P1", "text": CLEAN}],
        "changes": [{"id": "S1", "type": "G", "source_sentence": "x", "revised_sentence": "x"}],
        "audit": {"gate": "pass"},
    },
    "evidence": {"preserved": {}},
    "uncertainty": {"needs_author_confirmation": []},
}
rp = os.path.join(td, "result.json")
open(rp, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False))
v = vr.validate(rp, td)
check("T15 result 契约通过", v["valid"], str(v["errors"]))

print("\nTOTAL FAILURES: %d %s" % (len(FAILS), FAILS))
sys.exit(0 if not FAILS else 1)
