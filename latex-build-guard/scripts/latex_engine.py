#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
latex_engine.py — LaTeX 写作与编译的确定性核验引擎

面向 LaTeX 工程的高频易错动作，把四类能力做成可运行、可复核的计算：

  check_source        源码结构与宏包：主/子文件、导言区、宏包加载顺序、常见命令误用
  classify_errors     编译得通：把编译日志报错分类、定位到文件/行号/根因（不停在第一条）
  check_content       改得对：公式编号引用、表格数值列宽、交叉引用与 .bib 对应、模板必填项
  check_deliverable   交得可用：交付 .tex 源码而非 PDF/截图；结构清楚可编辑
  check_reproducibility 复现得了：模板版本/宏包/字体/编译命令轮次是否记录
  pipeline            串联以上，产出结构化结果与证据链

设计原则：
  - 纯 Python 3 标准库，无第三方依赖、无网络请求、不实际调用 TeX 编译器；
  - 对"编译日志"做静态解析与分类，对源码做静态规则检查；真正的编译验证由 Agent 在
    平台环境执行，脚本给它结构化的错误清单与修复建议；
  - 缺宏包、缺字体、报错级联、模板类缺失、权限不足一律显式标注，绝不臆造编译成功或产物。

用法：
  python latex_engine.py --help
  python latex_engine.py pipeline input.json > result.json
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
def _lines(text: str) -> List[str]:
    return (text or "").splitlines()


# ---------------------------------------------------------------------------
# 1) 源码结构与宏包
# ---------------------------------------------------------------------------
KNOWN_PACKAGES = {
    "amsmath", "amssymb", "amsthm", "geometry", "graphicx", "booktabs", "multirow",
    "multicol", "caption", "subfigure", "subcaption", "hyperref", "cleveref", "cite",
    "natbib", "biblatex", "inputenc", "fontenc", "fontspec", "ctex", "babel", "titlesec",
    "titling", "fancyhdr", "enumitem", "xcolor", "color", "array", "tabularx", "longtable",
    "siunitx", "pgfplots", "tikz", "listings", "minted", "algorithm", "algorithmic",
    "graphicx", "float", "placeins", "setspace", "parskip", "microtype", "csquotes",
}
# 加载顺序约束（真实 LaTeX 经验）：
#   - amsmath/xcolor 等应在 hyperref 之前；
#   - cleveref/cite/natbib/biblatex 等交叉引用包应在 hyperref 之后，
#     否则 \cref 的类型名/链接可能失效或引用编号错乱。
BEFORE_HYPERREF = {"amsmath", "amssymb", "xcolor"}
AFTER_HYPERREF = {"cleveref", "cite", "natbib", "biblatex"}


def check_source(main_tex: str, sub_files: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """静态检查 LaTeX 源码结构与宏包使用。"""
    sub_files = sub_files or {}
    issues = []

    # 文档类
    has_docclass = bool(re.search(r"\\documentclass\b", main_tex or ""))
    if not has_docclass:
        issues.append({"type": "missing_docclass", "severity": "error",
                       "reason": "找不到 \\documentclass，可能不是主文件"})
    # begin/end document
    has_begin = bool(re.search(r"\\begin\{document\}", main_tex or ""))
    has_end = bool(re.search(r"\\end\{document\}", main_tex or ""))
    if not (has_begin and has_end):
        issues.append({"type": "document_env", "severity": "error",
                       "reason": "document 环境不完整（缺 \\begin 或 \\end）"})

    # 宏包
    pkgs = re.findall(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}", main_tex or "")
    pkg_set = set()
    for p in pkgs:
        pkg_set |= {x.strip() for x in p.split(",")}
    unknown = sorted(p for p in pkg_set if p and p not in KNOWN_PACKAGES)
    if unknown:
        issues.append({"type": "uncommon_package", "severity": "warning",
                       "reason": f"不常见/自定义宏包，须确认已安装：{unknown}", "packages": unknown})

    # 加载顺序：cleveref/cite 应在 hyperref 后，amsmath/xcolor 应在其前。
    # 用整段文本的字符偏移比较，兼容多个 \usepackage 写在同一行的情况。
    lines = _lines(main_tex)
    pkg_pat = r"\\usepackage(?:\[[^\]]*\])?\{[^}]*\b%s\b"
    def pkg_pos(name: str) -> int:
        m = re.search(pkg_pat % re.escape(name), main_tex or "")
        return m.start() if m else -1
    def pkg_line(name: str) -> int:
        for i, ln in enumerate(lines, 1):
            if re.search(pkg_pat % re.escape(name), ln):
                return i
        return -1
    hyp_pos = pkg_pos("hyperref")
    hyp = pkg_line("hyperref")
    if hyp_pos >= 0:
        for name in sorted(BEFORE_HYPERREF):
            p = pkg_pos(name)
            if p >= 0 and p > hyp_pos:
                pl = pkg_line(name)
                issues.append({"type": "package_order", "severity": "warning",
                               "reason": f"{name}(L{pl}) 在 hyperref(L{hyp}) 之后加载，易引发连锁错误"})
        # 交叉引用类宏包应在 hyperref 之后（此前这段逻辑缺失，属死代码）
        for name in sorted(AFTER_HYPERREF):
            p = pkg_pos(name)
            if 0 <= p < hyp_pos:
                pl = pkg_line(name)
                issues.append({"type": "package_order", "severity": "warning",
                               "reason": f"{name}(L{pl}) 在 hyperref(L{hyp}) 之前加载，交叉引用类型名/链接可能失效"})

    # 常见命令误用
    if r"\input" in (main_tex or "") or r"\include" in (main_tex or ""):
        refs = re.findall(r"\\(?:input|include)\{([^}]+)\}", main_tex or "")
        for r in refs:
            key = r if r.endswith(".tex") else r + ".tex"
            if key not in sub_files and r not in sub_files:
                issues.append({"type": "missing_subfile", "severity": "error",
                               "reason": f"引用子文件 {r} 但未提供其内容", "file": r})

    # 未闭合的花括号粗检（忽略注释行）
    body = "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in lines)
    opens, closes = body.count("{"), body.count("}")
    brace_balanced = opens == closes
    if not brace_balanced:
        issues.append({"type": "brace_unbalanced", "severity": "error",
                       "reason": f"花括号不平衡：{{ {opens} vs }} {closes}（含命令参数，须人工核对）"})

    has_error = any(i["severity"] == "error" for i in issues)
    return {
        "has_docclass": has_docclass,
        "document_env_complete": has_begin and has_end,
        "packages": sorted(pkg_set),
        "brace_balanced": brace_balanced,
        "issues": issues,
        "structure_ok": not has_error,
        "advice": ("源码结构无明显问题" if not has_error
                   else f"{sum(1 for i in issues if i['severity']=='error')} 处结构错误须先修复"),
    }


# ---------------------------------------------------------------------------
# 2) 编译得通：错误分类与定位
# ---------------------------------------------------------------------------
ERROR_PATTERNS = [
    ("undefined_control", r"Undefined control sequence", "未定义命令：检查拼写或漏加载宏包"),
    ("missing_file", r"I can't find file|File .* not found|Emergency stop", "缺文件：.tex/.cls/.sty/图片路径"),
    ("missing_package", r"LaTeX Error: File .*\.sty not found|Package .* not found", "缺宏包：安装或换用已有包"),
    ("missing_font", r"Font .* not found|font warning|Missing character", "缺字体：安装字体或改用可用字体"),
    ("unclosed_group", r"Runaway argument|There's no line here to end|Missing \} inserted", "花括号/环境未闭合"),
    ("math_error", r"Missing \$ inserted|Display math should end|Bad math environment delimiter", "数学环境定界错误"),
    ("reference_undefined", r"Reference .* undefined|Citation .* undefined|There were undefined references", "交叉引用/引用未解析：多编译几轮或补 label/bib"),
    ("float_overflow", r"Float too large|Overfull \\hbox|Overfull \\vbox", "浮动体/盒子溢出：调整列宽或版式"),
    ("table_error", r"Misplaced \\noalign|Illegal unit|Missing number|Extra alignment tab", "表格列数与内容不匹配"),
    ("package_conflict", r"Package .* Error|Option clash|not supported", "宏包冲突或选项冲突"),
    ("permission", r"Permission denied|I can't write file|Read-only", "权限不足：检查目录写权限"),
    ("general_error", r"^! |LaTeX Error|Fatal error", "其他 LaTeX 错误"),
]
WARNING_PATTERN = re.compile(r"Warning|Overfull|Underfull", re.I)


def classify_errors(compile_log: str) -> Dict[str, Any]:
    """解析编译日志，每条报错定位文件/行号/根因，返回完整清单（不停在第一条）。"""
    lines = _lines(compile_log)
    errors = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("!") or re.search(r"^! ", ln) or WARNING_PATTERN.search(ln):
            # 抓取紧随其后的 "l.123 ..." 行号信息（仅限紧邻 1-2 行，避免串到下一条错误）
            loc_file, loc_line = "", None
            snippet = ""
            # 错误信息自身可能带文件名
            fm0 = re.search(r"([^\s`:]+\.(?:tex|sty|cls|bib))", ln)
            if fm0:
                loc_file = fm0.group(1)
            j = i + 1
            while j < len(lines) and j <= i + 3:
                # 遇到下一条错误则停止，防止行号串位
                if lines[j].startswith("!") or WARNING_PATTERN.search(lines[j]):
                    break
                m = re.search(r"(?:^|\s)l\.(\d+)\s*(.*)", lines[j])
                if m:
                    loc_line = int(m.group(1))
                    snippet = m.group(2).strip()[:120]
                    break
                fm = re.search(r"(.+\.(?:tex|sty|cls|bib))", lines[j])
                if fm and not loc_file:
                    loc_file = fm.group(1)
                j += 1
            # 分类根因
            cat, cause = "other", "未匹配已知模式，须人工判断"
            for name, pat, desc in ERROR_PATTERNS:
                if re.search(pat, ln, re.I) or re.search(pat, " ".join(lines[i:i+3]), re.I):
                    cat, cause = name, desc
                    break
            is_warn = bool(WARNING_PATTERN.search(ln)) and not ln.startswith("!")
            errors.append({
                "line_no": i + 1, "log_excerpt": ln.strip()[:160],
                "type": "warning" if is_warn else "error",
                "category": cat, "cause": cause,
                "file": loc_file, "tex_line": loc_line, "snippet": snippet,
            })
        i += 1

    err_only = [e for e in errors if e["type"] == "error"]
    cats = {}
    for e in err_only:
        cats[e["category"]] = cats.get(e["category"], 0) + 1
    # 级联判断：多条错误同源
    cascading = len(cats) == 1 and len(err_only) >= 3
    return {
        "errors": errors,
        "error_count": len(err_only),
        "warning_count": sum(1 for e in errors if e["type"] == "warning"),
        "categories": cats,
        "cascading": cascading,
        "advice": ("编译日志无 error" if not err_only else
                  (f"共 {len(err_only)} 个错误，集中在 {list(cats)[0]}，可能是级联错误，先修根因"
                   if cascading else f"共 {len(err_only)} 个错误，按文件/行号逐条修复")),
    }


# ---------------------------------------------------------------------------
# 3) 改得对：公式/表格/引用/模板
# ---------------------------------------------------------------------------
def count_tabular_cols(spec: str) -> int:
    """正确解析 tabular 列格式串的列数。

    处理 l/c/r/p{..}/m{..}/b{..}/X 列类型，忽略竖线 |、@{..}、>{..}、<{..}、!{..}
    等仅修饰不占列的语法。此前用 r"[lcrp m b]" 字符类会把空格和 p{2cm} 内的字符
    误计为列，属确定性 bug。
    """
    s = spec or ""
    # 去掉不占列的修饰块（反复去，直到稳定）
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"[!@><]\{[^{}]*\}", "", s)
    s = s.replace("|", "")
    # 每个列类型算一列；p/m/b 后跟 {width} 只算一列
    s = re.sub(r"[pmb]\{[^{}]*\}", "C", s)
    return len(re.findall(r"[lcrCX]", s))


def check_table_rows(tex: str) -> List[Dict[str, Any]]:
    """核对每个 tabular 环境内各行的 & 数是否与列格式匹配（考虑 \\multicolumn）。"""
    issues = []
    env_re = re.compile(r"\\begin\{(tabular|tabularx|tabular\*)\}(?:\[[^\]]*\])?\{([^}]*)\}(.*?)\\end\{\1\}", re.S)
    for m in env_re.finditer(tex or ""):
        spec, body = m.group(2), m.group(3)
        ncols = count_tabular_cols(spec)
        if ncols == 0:
            issues.append({"type": "table_spec", "severity": "warning",
                           "reason": f"无法解析表格列格式：{spec[:40]}"})
            continue
        # 去掉注释后按 \\ 分行
        body = "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in body.splitlines())
        for row_no, row in enumerate(re.split(r"\\\\", body), 1):
            if not row.strip() or re.fullmatch(r"\s*[\\hline|\\cline{[^}]*}|\\toprule|\\midrule|\\bottomrule|\s]+", row.strip()):
                continue
            # 一行占用的列数 = (& 数 + 1) + Σ(multicolumn 多跨的 k-1 列)
            # 注意：& 数已把 multicolumn 计作 1 个单元格，它跨 k 列需补回 k-1。
            merge = sum(int(k) - 1 for k in re.findall(r"\\multicolumn\{(\d+)\}", row))
            cells = row.count("&") + 1 + merge
            if cells != ncols:
                issues.append({"type": "table_col_mismatch", "severity": "error",
                               "reason": f"表格第 {row_no} 行有 {cells} 个单元格，列格式定义 {ncols} 列",
                               "row": row_no, "cells": cells, "expected": ncols,
                               "excerpt": row.strip()[:60]})
    return issues


def check_content(tex: str, bib: Optional[str] = None,
                  required_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    issues = []

    # 公式：环境与引用
    eq_envs = len(re.findall(r"\\begin\{(?:equation|align|gather|multline|eqnarray)\*?\}", tex or ""))
    labels = set(re.findall(r"\\label\{([^}]+)\}", tex or ""))
    refs = set(re.findall(r"\\(?:ref|eqref|cref|Cref)\{([^}]+)\}", tex or ""))
    dangling_refs = sorted(refs - labels)
    if dangling_refs:
        issues.append({"type": "dangling_ref", "severity": "error",
                       "reason": f"\\ref 引用了不存在的 label：{dangling_refs}", "items": dangling_refs})
    bracket_labels = [k for k in labels if re.match(r"^(eq|fig|tab|sec|chap):", k)]
    if eq_envs and not any(k.startswith("eq:") for k in labels):
        issues.append({"type": "eq_label", "severity": "warning",
                       "reason": "有公式环境但无 eq: 命名标签，公式编号不便引用"})

    # 表格：正确解析列格式并逐行核对单元格数（含 multicolumn）
    issues.extend(check_table_rows(tex))

    # 引用：\cite 与 bib 条目对应
    cites = set()
    for m in re.findall(r"\\cite(?:\[[^\]]*\])?\{([^}]+)\}", tex or ""):
        cites |= {k.strip() for k in m.split(",")}
    bibkeys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", bib or "")) if bib else set()
    missing_cites = sorted(cites - bibkeys) if bib else []
    if bib and missing_cites:
        issues.append({"type": "cite_no_bib", "severity": "error",
                       "reason": f"\\cite 的键在 .bib 中找不到：{missing_cites}", "items": missing_cites})
    uncited = sorted(bibkeys - cites) if bib else []
    if bib and uncited:
        issues.append({"type": "bib_uncited", "severity": "warning",
                       "reason": f".bib 条目未被正文引用（{len(uncited)} 条）", "items": uncited[:10]})

    # 模板必填项
    required = required_fields or []
    missing_req = []
    for f in required:
        #  loosely check for a command or text marker
        if f.lower() not in (tex or "").lower() and ("\\" + f) not in (tex or ""):
            missing_req.append(f)
    if missing_req:
        issues.append({"type": "template_required", "severity": "error",
                       "reason": f"模板必填项缺失：{missing_req}", "items": missing_req})

    has_error = any(i["severity"] == "error" for i in issues)
    return {
        "equation_envs": eq_envs,
        "labels_count": len(labels),
        "refs_count": len(refs),
        "cites_count": len(cites),
        "bib_entries": len(bibkeys),
        "issues": issues,
        "content_ok": not has_error,
        "advice": ("公式/表格/引用/必填项检查通过" if not has_error
                   else f"{sum(1 for i in issues if i['severity']=='error')} 处内容错误须修复"),
    }


# ---------------------------------------------------------------------------
# 4) 交得可用：交付物
# ---------------------------------------------------------------------------
def check_deliverable(files: Dict[str, str]) -> Dict[str, Any]:
    """files: {文件名: 内容}。验证交付的是可编辑 .tex 源码。"""
    names = list(files.keys())
    tex_files = [n for n in names if n.lower().endswith(".tex")]
    binary_like = [n for n in names if re.search(r"\.(pdf|png|jpe?g|svg|docx)$", n, re.I)]
    issues = []
    if not tex_files:
        issues.append({"type": "no_tex", "severity": "error",
                       "reason": "交付物中没有 .tex 源码，PDF/截图不能作为结果"})
    if binary_like and not tex_files:
        issues.append({"type": "binary_only", "severity": "error",
                       "reason": f"只交付了二进制/图片文件：{binary_like}"})
    # 源码须有实质内容（非片段）
    for n in tex_files:
        content = files[n]
        if len(content.strip()) < 80 or not re.search(r"\\documentclass|\\begin\{document\}", content):
            issues.append({"type": "fragment", "severity": "warning",
                           "reason": f"{n} 可能是片段（无 document 结构或过短），须确认可独立编译", "file": n})
    has_error = any(i["severity"] == "error" for i in issues)
    return {
        "tex_files": tex_files,
        "aux_files": [n for n in names if n not in tex_files],
        "issues": issues,
        "usable": not has_error,
        "advice": ("交付物为可编辑源码" if not has_error else "交付物不合要求，须提供 .tex 源码"),
    }


# ---------------------------------------------------------------------------
# 5) 复现得了：构建记录
# ---------------------------------------------------------------------------
REPRO_ITEMS = {
    "tex_dist": {"label": "TeX发行版", "patterns": [r"texlive|miktex|TeX Live|发行版"]},
    "template_version": {"label": "模板版本", "patterns": [r"模板版本|template version|\.cls|\.sty|版本 v?\d"]},
    "packages": {"label": "宏包及版本", "patterns": [r"宏包|package|\.sty|版本"]},
    "fonts": {"label": "字体依赖", "patterns": [r"字体|font|fontspec|Times|Latin Modern|宋体"]},
    "compile_cmd": {"label": "编译命令", "patterns": [r"pdflatex|xelatex|lualatex|latexmk|编译命令"]},
    "rounds": {"label": "编译轮次", "patterns": [r"轮次|编译\d+次|two.?pass|多遍|-\d+\s*rounds|轮"]},
}


def check_reproducibility(record: str, required: Optional[List[str]] = None) -> Dict[str, Any]:
    required = required or list(REPRO_ITEMS.keys())
    items, missing = {}, []
    for key in required:
        meta = REPRO_ITEMS.get(key, {"label": key, "patterns": [key]})
        ok = any(re.search(p, record or "", re.I) for p in meta["patterns"])
        items[key] = {"label": meta["label"], "present": ok}
        if not ok:
            missing.append({"item": key, "label": meta["label"],
                            "hint": f"复现记录缺『{meta['label']}』"})
    return {
        "items": items,
        "present_count": sum(1 for v in items.values() if v["present"]),
        "required_count": len(required),
        "missing": missing,
        "reproducible": not missing,
        "advice": ("构建记录齐全，他人可复现" if not missing
                   else f"构建记录缺 {len(missing)} 项：{[m['label'] for m in missing]}"),
    }


# ---------------------------------------------------------------------------
# 6) pipeline
# ---------------------------------------------------------------------------
def pipeline(payload: Dict[str, Any], compact: bool = False) -> Dict[str, Any]:
    case_id = payload.get("case_id", "")
    main_tex = payload.get("main_tex", "") or ""
    sub_files = payload.get("sub_files", {}) or {}
    log = payload.get("compile_log", "") or ""
    bib = payload.get("bib", "") or ""
    files = payload.get("files", {}) or {}
    record = payload.get("build_record", "") or ""
    required_fields = payload.get("template_required_fields")

    r_src = check_source(main_tex, sub_files)
    r_err = classify_errors(log)
    r_content = check_content(main_tex, bib, required_fields)
    r_deliv = check_deliverable(files)
    r_repro = check_reproducibility(record, payload.get("required_repro"))

    overall = (r_src["structure_ok"] and r_err["error_count"] == 0 and
               r_content["content_ok"] and r_deliv["usable"] and r_repro["reproducible"])
    status = "ok" if overall else "needs_attention"

    if compact:
        # 省 token 模式：只回状态 + 各维度结论 + 需修问题清单，不重复原文/证据全文
        problems = []
        for i in r_src["issues"]:
            if i["severity"] == "error":
                problems.append({"where": "source", "type": i["type"], "reason": i["reason"]})
        for e in r_err["errors"]:
            if e["type"] == "error":
                problems.append({"where": "compile", "type": e["category"],
                                 "reason": e["cause"], "file": e["file"], "line": e["tex_line"]})
        for i in r_content["issues"]:
            if i["severity"] == "error":
                problems.append({"where": "content", "type": i["type"], "reason": i["reason"]})
        for i in r_deliv["issues"]:
            if i["severity"] == "error":
                problems.append({"where": "deliverable", "type": i["type"], "reason": i["reason"]})
        for m in r_repro["missing"]:
            problems.append({"where": "repro", "item": m["item"], "hint": m["hint"]})
        return {
            "case_id": case_id,
            "status": status,
            "summary": {
                "structure_ok": r_src["structure_ok"],
                "compile_errors": r_err["error_count"],
                "content_ok": r_content["content_ok"],
                "deliverable_usable": r_deliv["usable"],
                "reproducible": r_repro["reproducible"],
                "cascading": r_err["cascading"],
            },
            "problems": problems,
            "needs_compile_verify": True,
        }

    return {
        "case_id": case_id,
        "status": status,
        "result": {
            "source_check": r_src,
            "error_classification": r_err,
            "content_check": r_content,
            "deliverable_check": r_deliv,
            "reproducibility_check": r_repro,
        },
        "evidence": {
            "principles": {
                "编译得通": "报错定位到文件/行号/根因", "改得对": "公式表格引用与模板合规",
                "交得可用": "交付可编辑 .tex 源码", "复现得了": "构建环境与命令记录齐全",
            },
            "error_locations": [{"category": e["category"], "file": e["file"],
                                 "tex_line": e["tex_line"]} for e in r_err["errors"] if e["type"] == "error"],
            "dangling_refs": next((i["items"] for i in r_content["issues"] if i["type"] == "dangling_ref"), []),
        },
        "uncertainty": {
            "needs_compile_verify": True,
            "note": ("本引擎只做静态检查与日志解析，不实际调用 TeX 编译器；"
                     "真正的编译通过须 Agent 在平台环境用记录的命令与轮次验证，不得臆造编译成功"),
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
    p = argparse.ArgumentParser(description="LaTeX 写作与编译确定性核验引擎")
    sub = p.add_subparsers(dest="cmd")
    for name, helptext in [
        ("check-source", "源码结构与宏包"),
        ("classify-errors", "编译得通：错误分类定位"),
        ("check-content", "改得对：公式表格引用"),
        ("check-deliverable", "交得可用：交付物校验"),
        ("check-reproducibility", "复现得了：构建记录"),
    ]:
        sp = sub.add_parser(name, help=helptext); sp.add_argument("input", help="JSON 输入")
    pp = sub.add_parser("pipeline", help="端到端")
    pp.add_argument("input", help="JSON 全量输入")
    pp.add_argument("--compact", action="store_true", help="省 token：只回状态与待修问题清单")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help(); return 0

    if args.cmd == "check-source":
        d = _load(args.input); out = check_source(d.get("main_tex", ""), d.get("sub_files"))
    elif args.cmd == "classify-errors":
        out = classify_errors(_load(args.input).get("compile_log", ""))
    elif args.cmd == "check-content":
        d = _load(args.input); out = check_content(d.get("tex", ""), d.get("bib"), d.get("required_fields"))
    elif args.cmd == "check-deliverable":
        out = check_deliverable(_load(args.input).get("files", {}))
    elif args.cmd == "check-reproducibility":
        d = _load(args.input); out = check_reproducibility(d.get("record", ""), d.get("required"))
    elif args.cmd == "pipeline":
        out = pipeline(_load(args.input), compact=args.compact)
    else:
        p.print_help(); return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
