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
from collections import defaultdict
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
# 注意：英文冒号 ':' 后不能紧跟数字，否则 "8:2 / 7:3" 这类比例会被误拆成
# 参数名=8、值=2（产生假阳性）。比例的形如 \d+:\d+ 应先被整体排除。
CLAIM_NUM_RE = re.compile(r"([A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff\s]{0,18}?)"
                          r"(?:为|是|=|：|:(?!\d)|设为|设置为)\s*(-?\d+(?:\.\d+)?)\s*(%|‰|e-?\d+)?", re.I)


def _extract_numbers(text: str) -> set:
    """抽取文本中所有数值 token（保留小数与科学计数）。"""
    out = set()
    for m in re.finditer(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", text or "", re.I):
        out.add(m.group(0))
    return out


# 来源里的 "name=value" / "name: value" 形式，用于参数名语义对齐
SRC_KV_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]{0,30})\s*[=:]\s*(-?\d+(?:\.\d+)?(?:e-?\d+)?)\s*(%|‰)?", re.I)
# 常见参数别名（正文中文名 ↔ 配置键名）
PARAM_ALIAS = {
    "学习率": {"lr", "learning_rate", "learningrate"},
    "learning rate": {"lr", "learning_rate", "learningrate"},
    "随机种子": {"seed", "random_seed", "randseed"},
    "批大小": {"batch", "batch_size", "bs"},
    "批量大小": {"batch", "batch_size", "bs"},
    "轮数": {"epochs", "epoch", "num_epochs"},
    "准确率": {"acc", "accuracy", "accuary"},
    "精确率": {"precision"},
    "召回率": {"recall", "rec"},
    "f1": {"f1", "f1_score"},
}


def _canon_param(name: str) -> str:
    n = _norm(name)
    return n


def _name_aligned(param_name: str, src_kv: Dict[str, set]) -> bool:
    """正文参数名是否与来源里的键语义对齐（含别名）。"""
    cn = _canon_param(param_name)
    if not cn:
        return False
    if cn in src_kv:
        return True
    aliases = set()
    for zh, ens in PARAM_ALIAS.items():
        if zh in cn:
            aliases |= ens
    # 正文名本身是英文键（如 lr）
    for key in src_kv:
        if key in cn or cn in key:
            return True
    return bool(aliases & set(src_kv.keys()))


def verify_values(manuscript: str, sources: Dict[str, str]) -> Dict[str, Any]:
    """核验正文声称的"参数名 = 数值"能否在来源中按【参数名+数值】联合定位。

    来源形如 `lr=0.001 seed=42 batch=32`。改进点（相对旧版"数值集合比对"）：
      - 先按来源里的 name=value 建立键值索引；
      - 正文每条 claim 只有在"参数名对齐 且 数值一致"时才算 found；
      - 仅数值存在但参数名对不上 → value_exists_name_mismatch（弱证据，不计入 supported）；
      - 彻底找不到 → unsupported（疑似补造）。
    8:2 / 7:3 这类比例由 CLAIM_NUM_RE 的 `(?!\\d)` 排除，不会被误拆。
    """
    src_kv: Dict[str, set] = defaultdict(set)
    all_src = ""
    if isinstance(sources, dict):
        for sname, stext in sources.items():
            all_src += "\n" + str(stext)
            for m in SRC_KV_RE.finditer(str(stext)):
                src_kv[m.group(1).lower()].add((m.group(2) + (m.group(3) or "")).rstrip("%‰"))
    else:
        all_src = str(sources)
        for m in SRC_KV_RE.finditer(all_src):
            src_kv[m.group(1).lower()].add((m.group(2) + (m.group(3) or "")).rstrip("%‰"))
    src_nums = _extract_numbers(all_src)

    claims = []
    for m in CLAIM_NUM_RE.finditer(manuscript or ""):
        name = m.group(1).strip()
        val = m.group(2) + (m.group(3) or "")
        val_key = val.rstrip("%‰")
        name_ok = _name_aligned(name, src_kv)
        value_ok = val_key in src_nums
        # 参数名对齐且该键下确有此值 → 强证据
        kv_ok = any(val_key in vals for key, vals in src_kv.items()
                    if key in [_canon_param(name).lower()] or
                    _name_aligned(name, {key: vals}))
        if name_ok and kv_ok:
            status = "found"
        elif value_ok:
            status = "value_exists_name_mismatch"
        else:
            status = "unsupported"
        matched_sources = [k for k, v in (sources.items() if isinstance(sources, dict) else [])
                           if val_key in _extract_numbers(v)] if value_ok else []
        claims.append({"claim": m.group(0).strip(), "parameter": name, "value": val,
                       "status": status,
                       "found_in_sources": status == "found",
                       "name_aligned": name_ok, "value_exists": value_ok,
                       "sources": matched_sources if status == "found" else []})
    weak = [c for c in claims if c["status"] == "value_exists_name_mismatch"]
    unsupported = [c for c in claims if c["status"] == "unsupported"]
    return {
        "claims": claims,
        "claim_count": len(claims),
        "found_count": sum(1 for c in claims if c["status"] == "found"),
        "weak_count": len(weak),
        "weak_name_mismatch": weak,
        "unsupported_count": len(unsupported),
        "unsupported": unsupported,
        "all_supported": not unsupported and not weak,
        "advice": ("正文数值均按参数名对齐在来源中定位" if not unsupported and not weak
                   else (f"{len(unsupported)} 处数值未在来源找到（疑似补造）；"
                         f"{len(weak)} 处数值存在但参数名对不上（须核对是否同一参数）")),
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
def render_draft(payload: Dict[str, Any]) -> Dict[str, Any]:
    """把核验结果渲染为【可编辑、可复做的六要素章节成稿草稿】。

    完成器核心：脚本自己用真实材料字段把章节写出来，不再只 check 别人稿子。
    硬约束：
      - 只用 section_text 原句、params、sources、gaps、limitations 的真实字段；
      - 每个数值/参数附来源（source），无来源用〔待核实〕标注，不补造；
      - 材料缺口进"作者确认清单"，不写成既成事实。
    """
    p = pipeline(payload)
    r = p["result"]
    section = payload.get("section_text", "") or ""
    params = payload.get("params", []) or []

    blocks: List[Dict[str, Any]] = []
    used_sources: List[str] = []

    # 六要素：每条从原文里取真实句子（按要素模式命中），无则标注缺口
    sent_units = [s.strip() for ln in section.splitlines()
                  for s in re.split(r"(?<=[。！？；.!?;])", ln) if s.strip()]
    def sentences_for(key):
        pats = ELEMENTS.get(key, {}).get("patterns", [])
        return [s for s in sent_units if _has(s, pats)]

    ordered_keys = ["steps", "setup", "params", "data", "baseline", "repro_limit"]
    for key in ordered_keys:
        label = ELEMENTS[key]["label"]
        sents = sentences_for(key)
        if sents:
            text = "".join(sents)
            status = "ok"
        else:
            text = "〔待核实：材料未提供『%s』的可引用表述，须补充原文定位〕" % label
            status = "needs_attention"
        blocks.append({"element": key, "label": label, "text": text, "status": status})

    # 参数表：用真实 params + source
    param_lines = []
    for row in r["parameter_table"]["rows"]:
        src = row["source"] or "〔待核实：无来源〕"
        val = row["value"]
        unit = row["unit"]
        line = "- %s = %s%s（来源：%s）" % (row["name"], val, unit, src)
        param_lines.append(line)
        if row["source"]:
            used_sources.append(row["source"])
    param_text = "\n".join(param_lines) if param_lines else "〔待核实：无参数表〕"
    blocks.append({"element": "param_table", "label": "参数表", "text": param_text,
                   "status": "ok" if r["parameter_table"]["all_sourced"] else "needs_attention"})

    # 数值核验：按来源定位的情况写入证据，补造/名实不符单列
    v = r["value_verification"]
    ev_lines = ["%s（%s）" % (c["claim"], "、".join(c["sources"]) or "无来源")
                for c in v["claims"] if c["status"] == "found"]
    ev_text = "\n".join(ev_lines) if ev_lines else "〔无可在来源定位的数值〕"
    problems = ([c["claim"] for c in v["unsupported"]] +
                [c["claim"] + "（参数名不符）" for c in v.get("weak_name_mismatch", [])])

    # 作者确认清单：缺口 + 套话限制
    confirm = [q["question"] for q in r["gap_probe"]["open_questions"]]
    confirm += [g["reason"] for g in r["gap_probe"]["generic_limitations"]]

    full_text = "\n\n".join("%s\n%s" % (b["label"], b["text"]) for b in blocks)
    all_ok = all(b["status"] == "ok" for b in blocks) and not problems and not confirm
    return {
        "case_id": payload.get("case_id", ""),
        "status": "draft" if all_ok else "partial",
        "draft_text": full_text,
        "blocks": blocks,
        "parameter_table": r["parameter_table"]["rows"],
        "value_evidence": ev_text,
        "source_refs": sorted(set(used_sources)),
        "needs_author_confirmation": confirm,
        "unverified_values": problems,
        "uncertainty": ["只按真实字段成稿，无来源参数/数值用〔待核实〕标注，不补造",
                        "数值同一条件、限制是否成立须结合配置/日志/原文复核"],
        "note": ("可编辑可复做章节草稿：六要素 + 参数表(带来源) + 证据定位 + 作者确认清单；"
                 "非最终稿，价值判断须人工核对"),
    }


def pipeline(payload: Dict[str, Any], with_draft: bool = False) -> Dict[str, Any]:
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
    # 成稿：with_draft=True 时由脚本用真实字段渲染，不再只透传外部 draft
    draft_obj = render_draft(payload) if with_draft else None
    method_draft = (draft_obj["draft_text"] if draft_obj else
                    payload.get("draft", ""))
    return {
        "case_id": case_id,
        "status": "ok" if overall else "needs_attention",
        "result": {
            "completeness": r_comp,
            "value_verification": r_val,
            "reproducibility": r_repro,
            "gap_probe": r_gap,
            "parameter_table": r_param,
            "method_experiment_draft": method_draft,
            "draft_detail": draft_obj,
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


def _write_solution(result: Dict[str, Any], out_dir: str, case_id: str) -> Dict[str, Any]:
    import os as _os
    payload = dict(result)
    if "case_id" not in payload:
        payload["case_id"] = case_id
    path = _os.path.join(out_dir, "result.json")
    try:
        _os.makedirs(out_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        ok = _os.path.exists(path) and _os.path.getsize(path) > 0
        return {"written": ok, "path": path, "bytes": _os.path.getsize(path) if ok else 0}
    except Exception as e:
        return {"written": False, "path": path, "error": type(e).__name__}


def _adapt_materials(payload: Dict[str, Any], case_dir: str) -> Dict[str, str]:
    """真实材料适配器：把 source_files/materials 指向的文件读成 {来源名: 文本}。

    支持：payload.sources(内联) + payload.source_files([路径] 或 {名:路径})
    + payload.materials({名:路径})。读不到不臆造，记录到 adapter_notes。
    """
    import os as _os
    sources: Dict[str, str] = {}
    for k, v in (payload.get("sources", {}) or {}).items():
        if isinstance(v, str):
            sources[k] = v
    files = payload.get("source_files") or payload.get("materials") or {}
    if isinstance(files, list):
        files = {_os.path.basename(str(f)): str(f) for f in files}
    for name, rel in files.items():
        path = rel if _os.path.isabs(str(rel)) else _os.path.join(case_dir, str(rel))
        try:
            sources[name] = open(path, encoding="utf-8").read()
        except Exception:
            pass  # 读不到不臆造，交给缺口清单提示
    return sources


def solve(case_path: str, out_dir: str) -> Dict[str, Any]:
    """端到端完成器：读 case.json → 适配真实材料 → 六要素检查 → 成稿 → 装配 result.json。"""
    import os as _os
    payload: Dict[str, Any] = {"case_id": ""}
    case_dir = _os.path.dirname(_os.path.abspath(case_path)) if case_path != "-" else "."
    if case_path and case_path != "-":
        try:
            loaded = _load(case_path)
            if isinstance(loaded, dict):
                payload = loaded
        except Exception as e:
            payload = {"case_id": "", "input_error": type(e).__name__}
    cid = str(payload.get("case_id", "") or "")

    if not (payload.get("section_text") or payload.get("draft") or
            payload.get("params") or payload.get("sources") or
            payload.get("source_files") or payload.get("materials")):
        result = {"case_id": cid, "status": "needs_attention", "input_mode": "case",
                  "result": {"summary": "输入无 section_text/材料，无法成稿（不伪造内容）"},
                  "needs_review": ["请提供 section_text 或材料文件"]}
        result["delivery"] = _write_solution(result, out_dir, cid)
        return result

    work = dict(payload)
    work["sources"] = _adapt_materials(payload, case_dir)
    pl = pipeline(work, with_draft=True)
    draft = pl["result"].get("draft_detail") or {}
    result = {
        "case_id": cid,
        "status": pl["status"],
        "input_mode": "case",
        "source_count": len(work["sources"]),
        "result": {
            "draft_text": draft.get("draft_text", pl["result"]["method_experiment_draft"]),
            "blocks": draft.get("blocks", []),
            "parameter_table": draft.get("parameter_table", []),
            "value_evidence": draft.get("value_evidence", ""),
            "source_refs": draft.get("source_refs", []),
            "status_checks": pl["status"],
            "summary": pl["result"],
        },
        "needs_review": draft.get("needs_author_confirmation", []) +
                        draft.get("unverified_values", []),
        "uncertainty": draft.get("uncertainty", []),
    }
    result["delivery"] = _write_solution(result, out_dir, cid)
    return result


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

    sp = sub.add_parser("render-draft", help="可复做章节成稿草稿：仅用真实字段渲染六要素")
    sp.add_argument("input", help="JSON 全量输入")

    sv = sub.add_parser("solve", help="端到端完成器：case.json →(适配材料)→ 成稿 → result.json")
    sv.add_argument("case", help="case.json 路径")
    sv.add_argument("--out", default="/app/output", help="交付目录")

    pl = sub.add_parser("pipeline", help="端到端")
    pl.add_argument("input", help="JSON 全量输入")
    pl.add_argument("--with-draft", action="store_true", help="脚本渲染成稿草稿")

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
    elif args.cmd == "render-draft":
        out = render_draft(_load(args.input))
    elif args.cmd == "solve":
        out = solve(args.case, args.out)
    elif args.cmd == "pipeline":
        out = pipeline(_load(args.input), with_draft=getattr(args, "with_draft", False))
    else:
        p.print_help(); return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
