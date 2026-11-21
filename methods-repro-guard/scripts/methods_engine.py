#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
methods_engine.py — 方法与实验章节写作的确定性核验引擎

面向学术论文"方法与实验"环节的高频易错动作，把它们从 LLM 自由发挥
变成可运行、可复核、可回溯的确定性计算：

  check_completeness   写得全：六类要素（步骤/设置/参数/数据/对照/复现限制）是否齐全
  verify_values        写得准：正文数值与配置/日志/代码来源交叉核验，检出补造数值
  check_reproducibility 做得着：复现清单（版本/环境/种子/命令/数据获取）是否给全
  probe_gaps           说得住：材料缺口显式追问 + 限制条件具体化（非套话）
  build_param_table    参数表：名称/取值/单位/作用对象/来源 结构化
  pipeline             串联以上，产出结构化结果与证据链

设计原则：
  - 纯 Python 3 标准库，无第三方依赖、无网络请求；
  - 只做确定性结构计算与规则判定，价值判断（数值是否真一致、限制是否真成立）
    留给 Agent，但要求给出可回溯定位；
  - 材料不足、来源缺失、配置冲突、数值无来源一律显式标注，绝不臆造数值或实验条件。

用法：
  python methods_engine.py --help
  python methods_engine.py pipeline input.json > result.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    s = (s or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z\u4e00-\u9fff.]+", " ", s)).strip()


def _has(s: str, patterns: List[str]) -> bool:
    return any(re.search(p, s or "", re.I) for p in patterns)


# ---------------------------------------------------------------------------
# 1) 写得全：六类要素完整性
# ---------------------------------------------------------------------------
ELEMENTS = {
    "steps": {
        "label": "方法步骤",
        "patterns": [r"步骤", r"流程", r"首先|然后|接着|最后", r"算法", r"\bstep\b", r"\bprocedure\b",
                     r"输入|输出|判断条件", r"\binput\b|\boutput\b"],
    },
    "setup": {
        "label": "实验设置",
        "patterns": [r"实验设置", r"硬件|软件|环境|版本|gpu|cpu|python|pytorch|tensorflow",
                     r"训练|验证|测试|train|valid|test", r"随机种子|random.?seed|seed"],
    },
    "params": {
        "label": "参数",
        "patterns": [r"参数|超参|学习率|batch|epoch|learning.?rate|\blr\b", r"取值|设为|设置为|=",
                     r"\bparam|hyperparameter"],
    },
    "data": {
        "label": "数据集与划分",
        "patterns": [r"数据集|dataset|数据版本", r"划分|比例|训练集|验证集|测试集|split|ratio",
                     r"预处理|preprocess", r"规模|样本数|条数"],
    },
    "baseline": {
        "label": "对照实验",
        "patterns": [r"基线|baseline|对照|对比", r"指标|评价|metric|accuracy|f1|precision|recall",
                     r"统计显著|显著性|显著性检验|significance|p.?value", r"同预算|公平比较"],
    },
    "repro_limit": {
        "label": "可复现与限制",
        "patterns": [r"复现|reproduc", r"代码|仓库|github|command|命令", r"限制|局限|失效|不适用|limitation",
                     r"适用范围|boundary"],
    },
}


def check_completeness(section_text: str, required: Optional[List[str]] = None) -> Dict[str, Any]:
    """检查方法与实验章节六类要素是否齐全。

    section_text: 章节正文；也可是每类要素分别给（通过 required 指定必查项）。
    """
    required = required or list(ELEMENTS.keys())
    report = {}
    missing = []
    for key in required:
        meta = ELEMENTS.get(key, {"label": key, "patterns": [key]})
        present = _has(section_text, meta["patterns"])
        report[key] = {"label": meta["label"], "present": present}
        if not present:
            missing.append({"element": key, "label": meta["label"],
                            "hint": f"缺少『{meta['label']}』相关表述，请补写或说明材料缺口"})
    present_count = sum(1 for v in report.values() if v["present"])
    return {
        "elements": report,
        "present_count": present_count,
        "required_count": len(required),
        "missing": missing,
        "complete": not missing,
        "advice": ("六类要素齐全" if not missing
                   else f"缺 {len(missing)} 类要素，须补写或显式标注缺口：{[m['label'] for m in missing]}"),
    }


# ---------------------------------------------------------------------------
# 2) 写得准：正文数值 vs 来源交叉核验
# ---------------------------------------------------------------------------
NUM_RE = re.compile(r"(?<![A-Za-z])(-?\d+(?:\.\d+)?)\s*(%|‰)?")
# 从正文抽取"参数名 = 数值"或"数值 单位"型 token
CLAIM_NUM_RE = re.compile(r"([A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff\s]{0,18}?)"
                          r"(?:为|是|=|：|:|设为|设置为)\s*(-?\d+(?:\.\d+)?)\s*(%|‰|e-?\d+)?", re.I)


def _extract_numbers(text: str) -> set:
    """抽取文本中所有数值 token（保留小数与科学计数）。"""
    out = set()
    for m in re.finditer(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", text or "", re.I):
        out.add(m.group(0))
    return out


def verify_values(manuscript: str, sources: Dict[str, str]) -> Dict[str, Any]:
    """核验正文声称的数值能否在来源（配置/日志/代码/数据说明）中找到。

    sources: {来源名: 来源文本}。函数只做数值集合比对，给出 find/no-find；
    语义核对（同一参数、同一条件）由 Agent 结合定位完成。
    """
    all_src = "\n".join(sources.values()) if isinstance(sources, dict) else str(sources)
    src_nums = _extract_numbers(all_src)
    claims = []
    for m in CLAIM_NUM_RE.finditer(manuscript or ""):
        name = m.group(1).strip()
        val = m.group(2) + (m.group(3) or "")
        found = val.rstrip("%‰") in {n.rstrip("%‰") for n in src_nums}
        claims.append({"claim": m.group(0).strip(), "parameter": name, "value": val,
                       "found_in_sources": found,
                       "sources": [k for k, v in sources.items() if val.rstrip("%‰") in _extract_numbers(v)] if found else []})
    unsupported = [c for c in claims if not c["found_in_sources"]]
    return {
        "claims": claims,
        "claim_count": len(claims),
        "unsupported_count": len(unsupported),
        "unsupported": unsupported,
        "all_supported": not unsupported,
        "advice": ("正文数值均可在来源中定位" if not unsupported
                   else f"{len(unsupported)} 处数值未在来源中找到，须核对是否为补造，或补充来源"),
    }


# ---------------------------------------------------------------------------
# 3) 做得着：可复现清单
# ---------------------------------------------------------------------------
REPRO_ITEMS = {
    "code_version": {"label": "代码版本/commit", "patterns": [r"commit|版本|version|git|仓库|github|release"]},
    "env": {"label": "运行环境/依赖", "patterns": [r"环境|依赖|python|pytorch|tensorflow|cuda|conda|requirements|版本"]},
    "seed": {"label": "随机种子", "patterns": [r"随机种子|random.?seed|seed|固定种子"]},
    "command": {"label": "运行命令", "patterns": [r"命令|command|python\s+\w+\.py|bash|运行脚本|执行"]},
    "data_access": {"label": "数据获取方式", "patterns": [r"数据获取|下载|来源|dataset|公开数据集|申请|链接"]},
    "split_detail": {"label": "划分细节", "patterns": [r"划分|比例|split|随机划分|seed|分层|stratified"]},
}


def check_reproducibility(text: str, required: Optional[List[str]] = None) -> Dict[str, Any]:
    required = required or list(REPRO_ITEMS.keys())
    items = {}
    missing = []
    for key in required:
        meta = REPRO_ITEMS.get(key, {"label": key, "patterns": [key]})
        ok = _has(text, meta["patterns"])
        items[key] = {"label": meta["label"], "present": ok}
        if not ok:
            missing.append({"item": key, "label": meta["label"],
                            "hint": f"复现清单缺『{meta['label']}』，读者可能无法复做实验"})
    n = sum(1 for v in items.values() if v["present"])
    return {
        "items": items,
        "present_count": n,
        "required_count": len(required),
        "missing": missing,
        "reproducible": not missing,
        "advice": ("复现清单齐全" if not missing
                   else f"复现清单缺 {len(missing)} 项，按 hint 补齐或标注无法提供"),
    }


# ---------------------------------------------------------------------------
# 4) 说得住：缺口追问 + 限制具体化
# ---------------------------------------------------------------------------
GENERIC_LIMIT = r"(还有一些不足|有待进一步|存在一定局限|仍需改进|尚需研究|future work|room to improve|一些限制)"


def probe_gaps(gaps: List[Dict[str, Any]], limitations: List[str],
               open_questions: Optional[List[str]] = None) -> Dict[str, Any]:
    """把材料缺口转成显式追问清单；把套话限制转成"落到具体失效场景"的要求。

    gaps: [{field, reason, ...}] 材料缺口
    limitations: 章节里的限制表述字符串列表
    """
    questions = []
    for g in gaps or []:
        field = g.get("field") or g.get("item") or g.get("element") or "未指明"
        reason = g.get("reason") or g.get("hint") or "材料不足"
        questions.append({"target": field, "question": f"请补充『{field}』的来源或取值（当前：{reason}）",
                          "source": g.get("source", "author_confirmation")})
    for q in open_questions or []:
        questions.append({"target": "作者确认", "question": q, "source": "author_confirmation"})

    generic_flags = []
    for lim in limitations or []:
        if re.search(GENERIC_LIMIT, lim, re.I):
            generic_flags.append({"text": lim,
                                  "reason": "套话式限制，须落到具体失效场景（何种数据/条件/范围内不成立）"})

    return {
        "open_questions": questions,
        "question_count": len(questions),
        "generic_limitations": generic_flags,
        "needs_author_confirmation": len(questions) > 0 or len(generic_flags) > 0,
        "advice": ("无待确认缺口，限制均已具体化" if not questions and not generic_flags
                   else f"有 {len(questions)} 项待补缺口，{len(generic_flags)} 条套话限制须具体化——显式标注并交作者确认，不得代填"),
    }


# ---------------------------------------------------------------------------
# 5) 参数表
# ---------------------------------------------------------------------------
def build_param_table(params: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成带名称/取值/单位/作用对象/来源的参数表，缺来源的显式标注。"""
    rows = []
    missing_source = []
    for p in params or []:
        src = str(p.get("source", "") or "").strip()
        row = {"name": p.get("name", ""), "value": p.get("value", ""),
               "unit": p.get("unit", ""), "scope": p.get("scope", ""),
               "source": src, "has_source": bool(src)}
        rows.append(row)
        if not src:
            missing_source.append({"name": p.get("name", ""),
                                   "hint": "参数无来源，须标注来自配置文件/日志/作者确认，不得补造"})
    return {
        "rows": rows,
        "param_count": len(rows),
        "missing_source": missing_source,
        "all_sourced": not missing_source,
        "advice": ("全部参数有来源" if not missing_source
                   else f"{len(missing_source)} 个参数无来源，须补来源或交作者确认"),
    }


# ---------------------------------------------------------------------------
# 6) pipeline
# ---------------------------------------------------------------------------
def pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    case_id = payload.get("case_id", "")
    section = payload.get("section_text", "")
    sources = payload.get("sources", {}) or {}
    params = payload.get("params", []) or []
    gaps = payload.get("gaps", []) or []
    limitations = payload.get("limitations", []) or []
    open_q = payload.get("open_questions", []) or []

    r_comp = check_completeness(section, payload.get("required_elements"))
    r_val = verify_values(section, sources)
    r_repro = check_reproducibility(section, payload.get("required_repro"))
    r_gap = probe_gaps(gaps + r_comp["missing"] + r_repro["missing"], limitations, open_q)
    r_param = build_param_table(params)

    # 汇总所有缺口成追问清单（去重）
    all_gaps = (r_comp["missing"] + r_repro["missing"] + r_val["unsupported"] +
                r_param["missing_source"])
    overall = (r_comp["complete"] and r_val["all_supported"] and r_repro["reproducible"]
               and r_param["all_sourced"] and not r_gap["generic_limitations"])
    return {
        "case_id": case_id,
        "status": "ok" if overall else "needs_attention",
        "result": {
            "completeness": r_comp,
            "value_verification": r_val,
            "reproducibility": r_repro,
            "gap_probe": r_gap,
            "parameter_table": r_param,
            "method_experiment_draft": payload.get("draft", ""),
        },
        "evidence": {
            "principles": {
                "写得全": "六类要素齐全", "写得准": "数值与来源一致、无补造",
                "做得着": "复现清单齐全", "说得住": "缺口显式追问、限制落到具体场景",
            },
            "unsupported_values": [c["claim"] for c in r_val["unsupported"]],
            "unsourced_params": [p["name"] for p in r_param["missing_source"]],
            "source_location": {c["claim"]: c["sources"] for c in r_val["claims"] if c["found_in_sources"]},
        },
        "uncertainty": {
            "open_questions": r_gap["open_questions"],
            "needs_author_confirmation": r_gap["needs_author_confirmation"],
            "gap_count": len(all_gaps),
            "note": ("数值是否同一条件、限制是否真成立属价值判断，须 Agent 结合配置/日志/原文定位复核；"
                     "脚本只做数值集合比对，不做语义等价判定"),
        },
    }


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
    p = argparse.ArgumentParser(description="方法与实验章节写作确定性核验引擎")
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("check-completeness", help="写得全：六要素完整性")
    sp.add_argument("input", help="JSON：section_text/required")

    sp = sub.add_parser("verify-values", help="写得准：数值交叉核验")
    sp.add_argument("input", help="JSON：manuscript/sources")

    sp = sub.add_parser("check-reproducibility", help="做得着：复现清单")
    sp.add_argument("input", help="JSON：text/required")

    sp = sub.add_parser("probe-gaps", help="说得住：缺口追问与限制具体化")
    sp.add_argument("input", help="JSON：gaps/limitations/open_questions")

    sp = sub.add_parser("build-param-table", help="参数表")
    sp.add_argument("input", help="JSON：params")

    sub.add_parser("pipeline", help="端到端").add_argument("input", help="JSON 全量输入")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 0

    if args.cmd == "check-completeness":
        d = _load(args.input); out = check_completeness(d.get("section_text", ""), d.get("required"))
    elif args.cmd == "verify-values":
        d = _load(args.input); out = verify_values(d.get("manuscript", ""), d.get("sources", {}))
    elif args.cmd == "check-reproducibility":
        d = _load(args.input); out = check_reproducibility(d.get("text", ""), d.get("required"))
    elif args.cmd == "probe-gaps":
        d = _load(args.input)
        out = probe_gaps(d.get("gaps", []), d.get("limitations", []), d.get("open_questions"))
    elif args.cmd == "build-param-table":
        d = _load(args.input); out = build_param_table(d.get("params", []))
    elif args.cmd == "pipeline":
        out = pipeline(_load(args.input))
    else:
        p.print_help(); return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
