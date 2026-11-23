#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_result.py — 结果契约与交付物自检

检查：
  - case_id / status / result / evidence / uncertainty 顶层字段；
  - 主产物字段（polished_text/revised_text/final_text/text）非空；
  - 逐句/逐段 changes 与 source_ref；
  - 审计 gate（若有）不是 fail；
  - 声明的交付文件真实存在且非空；
  - case.json 中 output_contract 要求的字段尽量覆盖。

用法：
  python scripts/validate_result.py --result /app/output/result.json \
      --outdir /app/output [--case /input/case.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

MAIN_KEYS = ("polished_text", "revised_text", "final_text", "text", "polished_manuscript")


def _get_contract_fields(case: Dict[str, Any]) -> List[str]:
    raw = None
    for key in ("output_contract", "outputContract", "required_fields", "expected_fields"):
        if key in case:
            raw = case[key]
            break
    fields: List[str] = []
    if isinstance(raw, dict):
        fields = [str(k) for k in raw.keys()]
    elif isinstance(raw, list):
        for x in raw:
            if isinstance(x, str):
                fields.append(x)
            elif isinstance(x, dict) and (x.get("name") or x.get("field") or x.get("key")):
                fields.append(str(x.get("name") or x.get("field") or x.get("key")))
    elif isinstance(raw, str):
        import re
        fields = re.findall(r"`([A-Za-z_][A-Za-z0-9_.-]{1,60})`", raw)
    return fields


def validate(result_path: str, outdir: str | None = None, case_path: str | None = None,
             main_field: str | None = None, min_chars: int = 20) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    p = Path(result_path)
    if not p.exists():
        return {"valid": False, "errors": ["result.json 不存在: %s" % result_path], "warnings": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"valid": False, "errors": ["result.json 不是合法 JSON: %s" % e], "warnings": []}
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["result.json 顶层必须是 object"], "warnings": []}

    for k in ("case_id", "status", "result", "evidence", "uncertainty"):
        if k not in data or data[k] in (None, "", {}, []):
            errors.append("缺少或为空: %s" % k)

    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    if main_field:
        if main_field not in result and main_field not in data:
            errors.append("缺少指定主产物字段: %s" % main_field)
        else:
            v = result.get(main_field, data.get(main_field))
            if isinstance(v, (list, dict)):
                if not v:
                    errors.append("主产物 %s 为空" % main_field)
            elif not isinstance(v, str) or len(v.strip()) < min_chars:
                errors.append("主产物 %s 过短或不是文本" % main_field)
        main_key = main_field
    else:
        main_key = next((k for k in MAIN_KEYS if result.get(k)), None)
        if not main_key:
            errors.append("result 中缺少主产物字段之一: %s" % ", ".join(MAIN_KEYS))
        else:
            text = result.get(main_key)
            if not isinstance(text, str) or len(text.strip()) < min_chars:
                errors.append("主产物 %s 过短或不是文本" % main_key)

    changes = result.get("changes") or data.get("changes")
    if not isinstance(changes, list) or not changes:
        warnings.append("缺少 changes 逐条修改记录（若确实无改动可忽略）")

    paras = result.get("paragraphs") or data.get("paragraphs")
    if isinstance(paras, list) and paras:
        for i, para in enumerate(paras, 1):
            if not isinstance(para, dict):
                warnings.append("paragraphs[%d] 不是对象" % i)
                continue
            if not (para.get("text") or para.get("revised") or para.get("target")):
                errors.append("paragraphs[%d] 缺少 text/revised" % i)
            if not (para.get("source_ref") or para.get("source_id") or para.get("source")):
                warnings.append("paragraphs[%d] 缺少 source_ref/source_id" % i)

    audit = result.get("audit") or data.get("audit")
    if isinstance(audit, dict) and audit.get("gate") == "fail":
        errors.append("audit.gate=fail，仍有 critical 违规未修")

    # 交付文件
    out_root = Path(outdir) if outdir else p.parent
    declared = []
    if isinstance(result.get("delivery"), dict):
        declared.append(result["delivery"].get("path"))
    for key in ("output_files", "files", "artifacts"):
        v = result.get(key)
        if isinstance(v, list):
            declared.extend(v)
    for d in declared:
        if not isinstance(d, str):
            continue
        q = Path(d)
        cand = q if q.is_absolute() else (out_root / q)
        if not cand.exists() or cand.stat().st_size == 0:
            errors.append("声明的交付文件不存在或为空: %s" % d)

    # output_contract
    if case_path and Path(case_path).exists():
        try:
            case = json.loads(Path(case_path).read_text(encoding="utf-8"))
            fields = _get_contract_fields(case)
            for f in fields:
                if f not in data and f not in result:
                    warnings.append("output_contract 字段未出现在 result 顶层或 result 内: %s" % f)
            cid = case.get("case_id") or case.get("id")
            if cid and str(data.get("case_id")) != str(cid):
                errors.append("case_id 不匹配: case=%s result=%s" % (cid, data.get("case_id")))
        except Exception as e:
            warnings.append("case.json 读取失败，未做契约比对: %s" % e)

    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "main_field": main_key, "result_path": str(p)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="result.json 契约与交付物自检")
    ap.add_argument("--result", required=True)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--case", default=None)
    ap.add_argument("--main-field", default=None, help="指定主产物字段，如 latex_source / nanopublications")
    ap.add_argument("--min-chars", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    r = validate(args.result, args.outdir, args.case, args.main_field, args.min_chars)
    print(json.dumps(r, ensure_ascii=False, indent=None if args.json else 2))
    return 0 if r["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
