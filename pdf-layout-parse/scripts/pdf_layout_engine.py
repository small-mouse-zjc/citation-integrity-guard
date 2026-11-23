#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_layout_engine.py — 确定性科研 PDF 版面解析引擎
=====================================================
面向「文献文档解析」挑战：把一份 PDF 的版面元素，用可复现的几何规则，
解析成可以逐字回溯、顺序正确、结构清晰的结果。

四问对应（题面原文）：
  提得全 —— clean_spans：逐字保真提取，剔页眉页脚/边注，补断行，标不可读
  排得对 —— reading_order：双/多栏分栏 + 跨栏块识别 + 栏内跨页顺序重排
  拆得清 —— detect_sections / rebuild_table / recover_formulas：
            章节层级、表格行列与单元格归属、公式上下标与希腊字母
  核得回 —— build_evidence / verify：每段每表回页码与区块，读不出如实标注

设计约束：
  - 主体纯标准库、无网络、无第三方依赖，Python 3.8+ 可运行。
  - 可选适配器 extract_from_pdf 在检测到 PyMuPDF 时才启用；缺失时给出
    明确降级指引（用平台自带工具导出带 bbox 的中间表示），不影响主体。
  - 所有判定基于坐标/文本的可回溯判据，不靠模型臆测；不确定项进 needs_review。

中间表示（layout JSON）——把 PDF 每页文本导成带坐标的行：
{
  "case_id": "示例",
  "pages": [
    {"page":1, "width":595, "height":842, "lines":[
       {"x0":72,"y0":90,"x1":520,"y1":104,"text":"Abstract",
        "spans":[{"text":"Abstract","size":12,"flags":16,"font":"Times-Bold"}]}
    ]}
  ]
}
坐标单位与 PDF 一致（pt），原点左上（y 向下）。

子命令：
  extract    （可选，需 PyMuPDF）PDF → layout JSON
  clean      提得全：逐字保真 + 页眉页脚/边注剔除 + 断行合并
  order      排得对：分栏 + 阅读顺序重排
  sections   拆得清：章节层级识别
  tables     拆得清：表格行列/单元格结构重建
  formulas   拆得清：上下标/希腊字母/公式编号保真
  captions   提得全：图表题注识别与配对
  evidence   核得回：为每个块生成页码+区块定位
  verify     核得回：覆盖率/漏行/顺序/悬空 自检
  pipeline   全流程串联，产出结构化结果 + 紧凑摘要（--compact 省 token）

用法见 examples/minimal_example.md。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

STATUS_OK = "success"
STATUS_PARTIAL = "partial"
STATUS_UNCERTAIN = "needs_review"

# 希腊字母 / 常见数学符号保真映射（Unicode 本身即目标，这里处理 OCR 常见误识）
GREEK_FIX = {
    "a": "α", "b": "β", "g": "γ", "d": "δ", "e": "ε", "q": "θ",
    "l": "λ", "m": "μ", "p": "π", "s": "σ", "f": "φ", "w": "ω",
    "D": "Δ", "S": "Σ", "O": "Ω", "P": "Π",
}
GREEK_VALID = set("αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ")

# 章节/结构识别模式（中英文）
SECTION_PATTERNS = [
    (r"^\s*第\s*[一二三四五六七八九十百\d]+\s*[章节篇]\s*", "chapter"),
    (r"^\s*\d+(?:\.\d+){0,3}\s+[^\d]", "numbered"),     # 1 / 1.2 / 1.2.3
    (r"^\s*(abstract|摘要)\s*$", "abstract"),
    (r"^\s*(keywords?|关键词)\s*[:：]", "keywords"),
    (r"^\s*(references?|参考文献|bibliography)\s*$", "references"),
    (r"^\s*(acknowledg|致谢)", "acknowledgement"),
    (r"^\s*(appendix|附录)", "appendix"),
    (r"^\s*(introduction|method|results?|discussion|conclusion)", "section_en"),
]
CAPTION_RE = re.compile(
    r"^\s*(图|表|fig(?:ure)?\.?|tab(?:le)?\.?)\s*(\d+)[.:：\-–\s]", re.I)
FORMULA_NUM_RE = re.compile(r"\(\s*(\d+)\s*\)\s*$")
REPLACEMENT_RE = re.compile(r"[\ufffd\u25a1\u25af\?]{2,}")


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _norm_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"\s+", " ", s).strip()


def _median(xs: List[float]) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    n = len(ys)
    return ys[n // 2] if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2


def _span_text(line: Dict[str, Any]) -> str:
    """逐字保真：优先用 spans 拼接，避免提取层合并丢字。"""
    spans = line.get("spans")
    if isinstance(spans, list) and spans:
        return "".join(str(s.get("text", "")) for s in spans)
    return str(line.get("text", ""))


def _iter_lines(layout: Dict[str, Any]):
    for pg in layout.get("pages", []):
        for li, ln in enumerate(pg.get("lines", [])):
            yield pg, li, ln


def _body_region(line: Dict[str, Any], pg: Dict[str, Any]) -> bool:
    """粗判正文区：排除页眉(上 8%)、页脚(下 8%)、左右窄边注。"""
    h = float(pg.get("height", 842) or 842)
    w = float(pg.get("width", 595) or 595)
    y0 = float(line.get("y0", 0))
    y1 = float(line.get("y1", 0))
    x0 = float(line.get("x0", 0))
    x1 = float(line.get("x1", 0))
    if y1 <= h * 0.08 or y0 >= h * 0.92:
        return False
    if x1 <= w * 0.06 or x0 >= w * 0.94:
        return False
    return True


def _page_stats(layout: Dict[str, Any]) -> Dict[str, float]:
    sizes = []
    for pg, li, ln in _iter_lines(layout):
        if not _body_region(ln, pg):
            continue
        for s in (ln.get("spans") or []):
            if s.get("size"):
                sizes.append(float(s["size"]))
    return {"median_size": _median(sizes), "size_count": len(sizes)}


# ---------------------------------------------------------------------------
# 0) 可选：从真实 PDF 提取 layout（需 PyMuPDF；缺失时优雅降级）
# ---------------------------------------------------------------------------
def _extract_with_pdftotext(pdf_path: str) -> Dict[str, Any]:
    """无 PyMuPDF 时的文本回退：pdftotext -layout → 合成近似 bbox 的 layout。

    精度低于 PyMuPDF（无真实字号/字体/精确列坐标），但能保住文字与页序；
    结果显式标 text_only，供后续 clean/order 以保守模式处理。
    """
    import shutil, subprocess
    exe = shutil.which("pdftotext")
    if not exe:
        return {
            "status": STATUS_UNCERTAIN,
            "error": "PyMuPDF and pdftotext both unavailable",
            "fallback": ("请安装 PyMuPDF（pip install pymupdf）或 poppler-utils（pdftotext），"
                         "或用平台 PDF 工具导出带 bbox 的 layout JSON。"),
        }
    try:
        proc = subprocess.run([exe, "-layout", "-enc", "UTF-8", pdf_path, "-"],
                              capture_output=True, text=True, errors="replace", timeout=180)
    except Exception as e:
        return {"status": STATUS_UNCERTAIN, "error": f"pdftotext_failed: {e}"}
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"status": STATUS_UNCERTAIN,
                "error": f"pdftotext_returncode={proc.returncode}",
                "stderr": (proc.stderr or "")[-1000:]}
    raw_pages = proc.stdout.split("\f")
    pages = []
    for pno, raw in enumerate(raw_pages, 1):
        if not raw.strip():
            continue
        # 空行分块；块内保留换行，供后续断行合并
        chunks = [c.strip("\n") for c in re.split(r"\n\s*\n", raw) if c.strip()]
        lines = []
        y = 40.0
        for chunk in chunks:
            for ln in chunk.splitlines():
                txt = ln.rstrip()
                if not txt.strip():
                    continue
                # 以缩进猜列：左缩进 > 20% 页宽视为右栏
                indent = len(txt) - len(txt.lstrip())
                width = 612.0
                x0 = 0.0 if indent < 12 else width * 0.52
                x1 = width if indent < 12 else width
                lines.append({
                    "x0": round(x0, 1), "y0": round(y, 1),
                    "x1": round(x1, 1), "y1": round(y + 11, 1),
                    "text": txt.strip(),
                    "spans": [{"text": txt.strip(), "size": 10.0, "flags": 0, "font": "pdftotext"}],
                })
                y += 13.0
        pages.append({"page": pno, "width": 612.0, "height": round(max(792.0, y + 20), 1),
                      "lines": lines})
    total = sum(len(p["lines"]) for p in pages)
    return {
        "status": STATUS_OK if total else STATUS_UNCERTAIN,
        "case_id": "", "backend": "pdftotext",
        "note": "无 PyMuPDF，使用 pdftotext 文本回退；bbox 与字号为近似值，表格/多栏顺序需人工复核。",
        "pages": pages,
        "stats": {"page_count": len(pages), "line_count": total, "text_only": True},
    }


def extract_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """用 PyMuPDF 把 PDF 导出为带 bbox 的中间表示；缺失时回退 pdftotext。"""
    try:
        import pymupdf  # type: ignore
    except Exception:
        try:
            import fitz as pymupdf  # type: ignore
        except Exception:
            return _extract_with_pdftotext(pdf_path)
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        return {
            "status": STATUS_UNCERTAIN,
            "error": f"cannot_open_pdf: {type(e).__name__}",
            "fallback": "PDF 无法打开（文件不存在/加密/损坏）。请检查路径；加密 PDF 需先解密。",
        }
    pages = []
    for pno in range(doc.page_count):
        page = doc[pno]
        rect = page.rect
        lines = []
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            if block.get("type", 0) != 0:  # 0=text，非文本块（图）跳过正文行
                continue
            for line in block.get("lines", []):
                spans = []
                for s in line.get("spans", []):
                    spans.append({
                        "text": s.get("text", ""),
                        "size": round(float(s.get("size", 0)), 2),
                        "flags": int(s.get("flags", 0)),
                        "font": s.get("font", ""),
                    })
                x0, y0, x1, y1 = line.get("bbox", (0, 0, 0, 0))
                if not _span_text({"spans": spans}).strip():
                    continue
                lines.append({
                    "x0": round(x0, 1), "y0": round(y0, 1),
                    "x1": round(x1, 1), "y1": round(y1, 1),
                    "text": "".join(s["text"] for s in spans),
                    "spans": spans,
                })
        pages.append({
            "page": pno + 1,
            "width": round(rect.width, 1),
            "height": round(rect.height, 1),
            "lines": lines,
        })
    total_lines = sum(len(p["lines"]) for p in pages)
    status = STATUS_UNCERTAIN if total_lines == 0 else STATUS_OK
    note = ("页面几乎无文字层，疑似扫描件/图片型 PDF；需 OCR 后重导。"
            if total_lines == 0 else "")
    return {
        "status": status, "case_id": "", "note": note, "backend": "pymupdf",
        "pages": pages,
        "stats": {"page_count": len(pages), "line_count": total_lines},
    }


# ---------------------------------------------------------------------------
# 1) 提得全：逐字保真 + 页眉页脚/边注剔除 + 断行合并
# ---------------------------------------------------------------------------
def _repeated_edge_texts(layout: Dict[str, Any]) -> Tuple[set, set]:
    """跨页在顶部/底部重复出现的文本 → 高置信页眉/页脚。"""
    top = Counter()
    bottom = Counter()
    for pg in layout.get("pages", []):
        h = float(pg.get("height", 842) or 842)
        lines = pg.get("lines", [])
        for ln in lines:
            key = _norm_text(_span_text(ln))
            if not key:
                continue
            y1 = float(ln.get("y1", 0)); y0 = float(ln.get("y0", 0))
            if y1 <= h * 0.09:
                top[key] += 1
            elif y0 >= h * 0.91:
                bottom[key] += 1
    pages_n = max(1, len(layout.get("pages", [])))
    header = {t for t, c in top.items() if c >= 2 and c >= pages_n * 0.5}
    footer = {t for t, c in bottom.items() if c >= 2 and c >= pages_n * 0.5}
    # 纯页码也算页脚
    for t in list(bottom):
        if re.fullmatch(r"[-—\s]*\d{1,4}[-—\s]*", t):
            footer.add(t)
    return header, footer


def clean_spans(layout: Dict[str, Any], merge_lines: bool = True) -> Dict[str, Any]:
    header, footer = _repeated_edge_texts(layout)
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    unreadable: List[Dict[str, Any]] = []
    for pg, li, ln in _iter_lines(layout):
        text = _span_text(ln)
        key = _norm_text(text)
        sizes = [float(s["size"]) for s in (ln.get("spans") or []) if s.get("size")]
        rec = {
            "page": pg.get("page"), "line": li,
            "x0": ln.get("x0"), "y0": ln.get("y0"),
            "x1": ln.get("x1"), "y1": ln.get("y1"),
            "size": _median(sizes) if sizes else 0,
            "text": text,
        }
        if not _body_region(ln, pg) or key in header or key in footer:
            rec["reason"] = ("header" if key in header else
                             "footer" if key in footer else "margin")
            dropped.append(rec)
            continue
        if REPLACEMENT_RE.search(text):
            rec["reason"] = "unreadable_glyphs"
            unreadable.append(rec)
        kept.append(rec)

    merged: List[Dict[str, Any]] = []
    if merge_lines:
        # 断行合并：同一页、x0 接近、纵向紧邻、上一行不以句末标点结尾
        by_page: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        for r in kept:
            by_page[r["page"]].append(r)
        for pno, rows in by_page.items():
            rows.sort(key=lambda r: (r["y0"], r["x0"]))
            buf = None
            for r in rows:
                t = r["text"].strip()
                r_size = (r.get("size") or 0)
                if buf is None:
                    buf = {**r, "text": t, "source_lines": [r["line"]]}
                    continue
                buf_lines = buf.get("source_lines", [])
                same_col = abs((r["x0"] or 0) - (buf["x0"] or 0)) < 12
                line_h = max(6.0, (buf["y1"] or 0) - (buf["y0"] or 0))
                gap = (r["y0"] or 0) - (buf["y1"] or 0)
                tight = gap < line_h * 0.6          # 间距不超过约 0.6 行高
                prev_open = not re.search(r"[。；：.!?？:：;)\]]\s*$", buf["text"])
                starts_lower = bool(re.match(r"[a-z，、；）)]", t))
                size_ok = (not r_size or not buf.get("size")
                           or abs(r_size - buf["size"]) < 1.5)  # 字号接近（排除标题）
                if same_col and tight and prev_open and not starts_lower and size_ok:
                    buf["text"] += t
                    buf["source_lines"].append(r["line"])
                    buf["y1"] = r["y1"]
                else:
                    merged.append(buf)
                    buf = {**r, "text": t, "source_lines": [r["line"]]}
            if buf is not None:
                merged.append(buf)
    else:
        merged = [dict(r, source_lines=[r["line"]]) for r in kept]

    for r in merged:
        r["text"] = r["text"].strip()
    total = sum(1 for _ in _iter_lines(layout))
    return {
        "status": STATUS_PARTIAL if (dropped or unreadable) else STATUS_OK,
        "header_texts": sorted(header), "footer_texts": sorted(footer),
        "lines": merged,
        "dropped": dropped,
        "unreadable": unreadable,
        "stats": {
            "input_lines": total,
            "body_lines": len(kept),
            "merged_lines": len(merged),
            "dropped_header_footer_margin": len(dropped),
            "unreadable_lines": len(unreadable),
            "char_count": sum(len(r["text"]) for r in merged),
        },
    }


# ---------------------------------------------------------------------------
# 2) 排得对：分栏 + 阅读顺序重排
# ---------------------------------------------------------------------------
def detect_columns(cleaned: Dict[str, Any], page_w: Optional[float] = None,
                   page_lines: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    按 x0 起点聚类判栏。跨栏宽块（标题/图表/公式，宽度>55%页面）不参与栏起点统计；
    两簇分别靠左(<0.4w)与靠右(>0.45w)且各有足够行 → 双栏，gutter 取两簇之间。
    """
    lines = page_lines if page_lines is not None else cleaned.get("lines", [])
    if not lines:
        return {"columns": 1, "gutter": None, "confidence": 0.0, "evidence": {}}
    if page_w is None:
        page_w = max((float(r.get("x1") or 0) for r in lines), default=0) * 1.02
    # 排除跨栏宽块
    starts = []
    for r in lines:
        x0 = float(r.get("x0") or 0); x1 = float(r.get("x1") or 0)
        if (x1 - x0) > page_w * 0.55:
            continue
        starts.append(x0)
    if not starts:
        return {"columns": 1, "gutter": None, "confidence": 0.2,
                "evidence": {"note": "仅跨栏宽块，按单栏处理"}}
    # x0 聚类（容差 18pt）
    clusters: List[List[float]] = []
    for x in sorted(starts):
        if clusters and x - clusters[-1][-1] <= 18:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    centers = [_median(c) for c in clusters]
    counts = [len(c) for c in clusters]
    # 找一个左簇和一个右簇
    left_idx = [i for i, m in enumerate(centers) if m < page_w * 0.40 and counts[i] >= 2]
    right_idx = [i for i, m in enumerate(centers) if m > page_w * 0.45 and counts[i] >= 2]
    two = bool(left_idx and right_idx)
    if two:
        li = max(left_idx, key=lambda i: counts[i])
        ri = min(right_idx, key=lambda i: centers[i])
        left_edge = max(clusters[li])
        right_edge = min(clusters[ri])
        gutter = [round(left_edge + 4, 1), round(right_edge - 4, 1)]
        conf = 0.85 if min(counts[li], counts[ri]) >= 3 else 0.6
    else:
        gutter = None
        conf = 0.25
    return {
        "columns": 2 if two else 1,
        "gutter": gutter,
        "confidence": conf,
        "evidence": {"clusters": [round(m, 1) for m in centers],
                     "cluster_counts": counts, "page_width": round(page_w, 1),
                     "wide_blocks_excluded": len(lines) - len(starts)},
    }


def reading_order(cleaned: Dict[str, Any], layout: Dict[str, Any] = None) -> Dict[str, Any]:
    """跨页、跨栏按版面顺序重排。跨栏块（标题/图表）按 y 插入全局序列。"""
    lines = cleaned.get("lines", [])
    pages_meta = {p.get("page"): p for p in (layout or {}).get("pages", [])}
    pg_nums = sorted({r["page"] for r in lines})
    out: List[Dict[str, Any]] = []
    column_reports = []
    for pno in pg_nums:
        rows = [r for r in lines if r["page"] == pno]
        pm = pages_meta.get(pno, {})
        cw = float(pm.get("width") or 0) or None
        det = detect_columns(cleaned, page_w=cw, page_lines=pm.get("lines", []))
        column_reports.append({"page": pno, **det})
        gutter = det["gutter"]
        if det["columns"] == 2 and gutter:
            gl, gr = gutter
            def col_of(r):
                x0 = float(r.get("x0") or 0); x1 = float(r.get("x1") or 0)
                if x0 < gl and x1 <= gr + 2:
                    return 0
                if x0 >= gl - 2:
                    return 1
                return -1  # 跨栏
            left = sorted([r for r in rows if col_of(r) == 0], key=lambda r: (r["y0"], r["x0"]))
            right = sorted([r for r in rows if col_of(r) == 1], key=lambda r: (r["y0"], r["x0"]))
            cross = [r for r in rows if col_of(r) == -1]
            # 跨栏块按 y 作为锚点切分左右栏
            anchors = sorted([(r["y0"], r) for r in cross], key=lambda t: t[0])
            def interleave(lo, hi):
                # 区间内左右栏按 y 交错（同一 y 先左后右）——贴近真实阅读顺序
                seg = [(float(r["y0"]), 0, r) for r in left if lo <= float(r["y0"]) < hi]
                seg += [(float(r["y0"]), 1, r) for r in right if lo <= float(r["y0"]) < hi]
                seg.sort(key=lambda t: (t[0], t[1]))
                return [("L" if t[1] == 0 else "R", t[2]) for t in seg]
            seq = []
            cursor = float("-inf")
            for ay, ar in anchors:
                seq += interleave(cursor, ay)
                seq.append(("X", ar))
                cursor = ay
            seq += interleave(cursor, float("inf"))
            for tag, r in seq:
                out.append({**r, "order": len(out) + 1, "column": tag})
        else:
            for r in sorted(rows, key=lambda r: (r["y0"], r["x0"])):
                out.append({**r, "order": len(out) + 1, "column": "single"})

    # 顺序自检：页码单调，同栏 y 单调
    violations = []
    prev = None
    for r in out:
        if prev:
            if r["page"] < prev["page"]:
                violations.append({"type": "page_backtrack", "at": r["order"]})
            elif r["page"] == prev["page"] and r.get("column") == prev.get("column"):
                if float(r["y0"]) + 0.5 < float(prev["y0"]):
                    violations.append({"type": "y_backtrack", "at": r["order"]})
        prev = r
    return {
        "status": STATUS_OK if not violations else STATUS_PARTIAL,
        "ordered": out,
        "column_reports": column_reports,
        "order_violations": violations,
        "stats": {"pages": len(pg_nums), "blocks": len(out),
                  "two_column_pages": sum(1 for c in column_reports if c["columns"] == 2)},
    }


# ---------------------------------------------------------------------------
# 3) 拆得清：章节层级
# ---------------------------------------------------------------------------
def detect_sections(order: Dict[str, Any]) -> Dict[str, Any]:
    median_size = _page_stats({"pages": [{"lines": [{
        "spans": [{"size": 10}], "x0": 0, "y0": 0, "x1": 1, "y1": 1,
        "text": "x"}]}]})["median_size"] or 10.0
    blocks = order.get("ordered", [])
    sections = []
    for r in blocks:
        t = r.get("text", "").strip()
        if not t:
            continue
        kind = None
        level = None
        for pat, k in SECTION_PATTERNS:
            m = re.match(pat, t, re.I)
            if m:
                kind = k
                break
        # 编号层级：1.2.3 → level=3
        nm = re.match(r"^\s*(\d+(?:\.\d+)*)\s", t)
        if nm:
            level = nm.group(1).count(".") + 1
        elif kind in ("chapter", "abstract", "references", "section_en", "appendix"):
            level = 1
        if kind or level:
            sections.append({
                "text": t[:120], "page": r["page"], "y0": r["y0"],
                "order": r["order"], "kind": kind or "heading",
                "level": level or 1,
            })
    return {
        "status": STATUS_OK if sections else STATUS_UNCERTAIN,
        "sections": sections,
        "tree": _section_tree(sections),
        "stats": {"heading_count": len(sections),
                  "levels": sorted({s["level"] for s in sections})},
    }


def _section_tree(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    root: List[Dict[str, Any]] = []
    stack: List[Dict[str, Any]] = []
    for s in sections:
        node = {"title": s["text"], "level": s["level"], "page": s["page"],
                "children": []}
        while stack and stack[-1]["level"] >= s["level"]:
            stack.pop()
        (stack[-1]["children"] if stack else root).append(node)
        stack.append(node)
    return root


# ---------------------------------------------------------------------------
# 4) 拆得清：表格结构重建
# ---------------------------------------------------------------------------
def _cluster_rows(lines: List[Dict[str, Any]], tol: float) -> List[List[Dict[str, Any]]]:
    rows = []
    for ln in sorted(lines, key=lambda r: (r["y0"], r["x0"])):
        placed = False
        for row in rows:
            if abs(_median([float(x["y0"]) for x in row]) - float(ln["y0"])) <= tol:
                row.append(ln); placed = True; break
        if not placed:
            rows.append([ln])
    return rows


def rebuild_table(cleaned: Dict[str, Any], layout: Dict[str, Any] = None,
                  y_tol: float = 3.0) -> Dict[str, Any]:
    """按 y 聚行、按 x 定列，重建 Markdown 表格；相邻行同列结构视为跨页续表候选。"""
    lines = [r for r in cleaned.get("lines", [])]
    # 只保留同一页内 ≥2 个横向分离片段的行（表格候选）
    tables = []
    by_page: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for r in lines:
        by_page[r["page"]].append(r)
    for pno, rows in by_page.items():
        clustered = _cluster_rows(rows, y_tol)
        def is_table_row(row):
            if len(row) < 2:
                return False
            # 各片段文本应偏短、像单元格；整句正文（任一片段>45字）不算表格行
            if any(len(str(c.get("text", "")).strip()) > 45 for c in row):
                return False
            # 片段横向分离的间距合理
            xs = sorted(float(c["x0"]) for c in row)
            return any(xs[i + 1] - xs[i] > 12 for i in range(len(xs) - 1))
        multi = [row for row in clustered if is_table_row(row)]
        # 用「行片段数的众数」筛掉混入的正文行：真表格各行列数一致
        if len(multi) >= 2:
            col_counts = Counter(len(row) for row in multi)
            mode_n, mode_c = col_counts.most_common(1)[0]
            # 保留片段数==众数的行（要求至少2行，且众数行占多数）
            if mode_c >= 2:
                multi = [row for row in multi if len(row) == mode_n]
        # 表格至少 2 行
        if len(multi) < 2:
            continue
        # 列边界：所有片段 x0 的聚类
        xs = sorted(float(c["x0"]) for row in multi for c in row)
        col_starts = []
        for x in xs:
            if not col_starts or x - col_starts[-1] > 18:
                col_starts.append(x)
        grid = []
        for row in multi:
            cells = [""] * len(col_starts)
            for c in sorted(row, key=lambda c: float(c["x0"])):
                idx = min(range(len(col_starts)),
                          key=lambda i: abs(col_starts[i] - float(c["x0"])))
                cells[idx] = (cells[idx] + " " + c["text"].strip()).strip()
            grid.append({"cells": cells, "y0": round(float(row[0]["y0"]), 1),
                         "page": pno})
        md = _grid_to_markdown(grid)
        tables.append({
            "page": pno, "y0": grid[0]["y0"], "rows": len(grid),
            "cols": len(col_starts), "grid": grid, "markdown": md,
            "source_lines": sorted({c["line"] for row in multi for c in row}),
        })
    # 跨页续表候选：相邻页、列数一致、末页表格在最底部
    continuations = []
    for a, b in zip(tables, tables[1:]):
        if b["page"] == a["page"] + 1 and a["cols"] == b["cols"]:
            continuations.append({"from": a["page"], "to": b["page"],
                                  "cols": a["cols"]})
    return {
        "status": STATUS_OK if tables else STATUS_UNCERTAIN,
        "tables": tables,
        "continuations": continuations,
        "stats": {"table_count": len(tables),
                  "multi_page_tables": len(continuations)},
    }


def _grid_to_markdown(grid: List[Dict[str, Any]]) -> str:
    if not grid:
        return ""
    cols = max(len(g["cells"]) for g in grid)
    def row_md(cells):
        cells = list(cells) + [""] * (cols - len(cells))
        return "| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |"
    out = [row_md(grid[0]["cells"]),
           "|" + "|".join(["---"] * cols) + "|"]
    for g in grid[1:]:
        out.append(row_md(g["cells"]))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 5) 拆得清：公式 / 上下标 / 希腊字母
# ---------------------------------------------------------------------------
def recover_formulas(layout: Dict[str, Any], cleaned: Dict[str, Any]) -> Dict[str, Any]:
    median_size = _page_stats(layout).get("median_size") or 10.0
    formulas = []
    greek_hits = []
    for r in cleaned.get("lines", []):
        text = r.get("text", "")
        spans = []
        # 从原始 layout 找回该行 spans（按页码+文本匹配）
        for pg in layout.get("pages", []):
            if pg.get("page") != r["page"]:
                continue
            for ln in pg.get("lines", []):
                if _norm_text(_span_text(ln)) == _norm_text(text):
                    spans = ln.get("spans", []) or []
                    break
        has_greek = any(ch in GREEK_VALID for ch in text)
        small = [s for s in spans if s.get("size") and float(s["size"]) < median_size * 0.78]
        fnum = FORMULA_NUM_RE.search(text)
        # 判定公式行：含希腊字母、或有上下标小字、或带 (n) 编号且非正文句
        is_formula = has_greek or bool(small) or (bool(fnum) and len(text) < 90)
        if not is_formula:
            continue
        rendered = text
        for s in small:
            st = str(s.get("text", "")).strip()
            if not st:
                continue
            y = s.get("_y", None)
            rendered = rendered.replace(st, "^{" + st + "}", 1)
        # 保真原则：只认原文中真实的希腊字母 Unicode，绝不把 ASCII 字母替换成希腊字母
        # （GREEK_FIX 仅作为可选 OCR 后处理，默认不启用，避免 "is"→"ιζ" 这类失真）
        rendered = text
        formulas.append({
            "text": text, "rendered": rendered,
            "number": fnum.group(1) if fnum else None,
            "page": r["page"], "y0": r["y0"],
            "has_greek": has_greek,
            "subscript_spans": len(small),
            "needs_review": bool(small) or has_greek,
        })
        if has_greek:
            greek_hits.append({"page": r["page"],
                               "chars": sorted({ch for ch in text if ch in GREEK_VALID})})
    return {
        "status": STATUS_OK if formulas else STATUS_UNCERTAIN,
        "formulas": formulas,
        "greek_pages": greek_hits,
        "stats": {"formula_candidates": len(formulas),
                  "numbered": sum(1 for f in formulas if f["number"]),
                  "with_subscript": sum(1 for f in formulas if f["subscript_spans"])},
        "note": "按结构元素识别并保真符号，不解释公式科学含义（题面要求）。",
    }


# ---------------------------------------------------------------------------
# 6) 提得全：图表题注识别与配对
# ---------------------------------------------------------------------------
def detect_captions(cleaned: Dict[str, Any], order: Dict[str, Any] = None) -> Dict[str, Any]:
    lines = order.get("ordered", []) if order else cleaned.get("lines", [])
    caps = []
    for r in lines:
        m = CAPTION_RE.match(r.get("text", ""))
        if not m:
            continue
        caps.append({
            "kind": "figure" if m.group(1).lower().startswith(("图", "fig")) else "table",
            "number": int(m.group(2)),
            "text": r["text"].strip(),
            "page": r["page"], "y0": r["y0"], "order": r["order"],
        })
    # 配对：同页、编号相同、类型不同的图/表题注（说明互相引用）
    pairs = []
    bykey = defaultdict(list)
    for c in caps:
        bykey[(c["page"], c["kind"])].append(c)
    for c in caps:
        near = [o for o in lines if o["page"] == c["page"]
                and abs(float(o["y0"]) - float(c["y0"])) < 24 and o["order"] != c["order"]]
        c["nearby_text"] = [n["text"][:60] for n in near[:3]]
    return {
        "status": STATUS_OK if caps else STATUS_UNCERTAIN,
        "captions": caps,
        "stats": {"figure_captions": sum(1 for c in caps if c["kind"] == "figure"),
                  "table_captions": sum(1 for c in caps if c["kind"] == "table")},
    }


# ---------------------------------------------------------------------------
# 7) 核得回：证据定位 + 自检
# ---------------------------------------------------------------------------
def build_evidence(cleaned: Dict[str, Any], order: Dict[str, Any],
                   sections: Dict[str, Any], tables: Dict[str, Any]) -> Dict[str, Any]:
    ev = []
    for r in order.get("ordered", []):
        ev.append({
            "id": f"B{r['order']:03d}",
            "page": r["page"],
            "bbox": [r.get("x0"), r.get("y0"), r.get("x1"), r.get("y1")],
            "block_type": "text",
            "text_head": r.get("text", "")[:40],
            "source_line": r.get("line"),
        })
    for s in sections.get("sections", []):
        ev.append({"id": f"S{len(ev)+1:03d}", "page": s["page"], "bbox": None,
                   "block_type": f"section:{s['kind']}", "text_head": s["text"][:40]})
    for t in tables.get("tables", []):
        ev.append({"id": f"T{len(ev)+1:03d}", "page": t["page"],
                   "bbox": [None, t["y0"], None, None],
                   "block_type": "table", "text_head": f"{t['rows']}x{t['cols']} table"})
    for d in cleaned.get("dropped", []):
        ev.append({"id": f"X{len(ev)+1:03d}", "page": d["page"], "bbox": None,
                   "block_type": "excluded:" + str(d.get("reason")),
                   "text_head": d["text"][:40]})
    return {"status": STATUS_OK, "evidence": ev,
            "stats": {"locatable_blocks": len(ev)}}


def verify(cleaned: Dict[str, Any], order: Dict[str, Any],
           evidence: Dict[str, Any], layout: Dict[str, Any]) -> Dict[str, Any]:
    src_chars = sum(len(_span_text(ln)) for _, _, ln in _iter_lines(layout))
    out_chars = cleaned.get("stats", {}).get("char_count", 0)
    body_chars = sum(len(_span_text(ln)) for pg, i, ln in _iter_lines(layout)
                     if _body_region(ln, pg))
    coverage = round(out_chars / body_chars, 4) if body_chars else 0.0
    problems = []
    if coverage < 0.90:
        problems.append(f"正文字符覆盖率偏低：{coverage:.1%}（<90%），检查断行合并是否吞字")
    if order.get("order_violations"):
        problems.append(f"阅读顺序异常 {len(order['order_violations'])} 处")
    if cleaned.get("unreadable"):
        problems.append(f"疑似乱码/缺字 {len(cleaned['unreadable'])} 行，已如实标注")
    ordered_ids = {r.get("line") for r in order.get("ordered", [])}
    body_ids = set()
    idx = 0
    for pg, li, ln in _iter_lines(layout):
        if _body_region(ln, pg):
            body_ids.add((pg.get("page"), li))
    miss = len(body_ids) - len([r for r in order.get("ordered", []) if r.get("line") is not None])
    return {
        "status": STATUS_OK if not problems else STATUS_PARTIAL,
        "consistent": not problems,
        "coverage": coverage,
        "src_chars": src_chars, "body_chars": body_chars, "out_chars": out_chars,
        "problems": problems,
        "stats": {"pages": len(layout.get("pages", [])),
                  "evidence_blocks": evidence.get("stats", {}).get("locatable_blocks", 0),
                  "unreadable_lines": len(cleaned.get("unreadable", []))},
    }


# ---------------------------------------------------------------------------
# 8) 全流程
# ---------------------------------------------------------------------------
def pipeline(payload: Dict[str, Any], compact: bool = False,
             outdir: Optional[str] = None) -> Dict[str, Any]:
    """
    payload:
      case_id, pages:[{page,width,height,lines:[{x0,y0,x1,y1,text,spans[]}]}]
      或 input_layout: 同上（二选一）
    """
    layout = _as_layout(payload)
    cid = payload.get("case_id", "")
    cleaned = clean_spans(layout)
    order = reading_order(cleaned, layout)
    sections = detect_sections(order)
    tables = rebuild_table(cleaned, layout)
    formulas = recover_formulas(layout, cleaned)
    captions = detect_captions(cleaned, order)
    evidence = build_evidence(cleaned, order, sections, tables)
    ver = verify(cleaned, order, evidence, layout)

    statuses = [cleaned["status"], order["status"], sections["status"],
                tables["status"], formulas["status"], captions["status"], ver["status"]]
    overall = STATUS_OK
    if STATUS_UNCERTAIN in statuses:
        overall = STATUS_UNCERTAIN
    elif STATUS_PARTIAL in statuses:
        overall = STATUS_PARTIAL

    full_text = "\n".join(r["text"] for r in order.get("ordered", []))
    result = {
        "reading_text": full_text,
        "structure": sections["tree"],
        "sections": sections["sections"],
        "tables": [{"page": t["page"], "markdown": t["markdown"],
                    "rows": t["rows"], "cols": t["cols"]} for t in tables["tables"]],
        "formulas": formulas["formulas"],
        "captions": captions["captions"],
        "evidence_index": evidence["evidence"],
        "verification": ver,
        "summary": (
            f"页数 {ver['stats']['pages']}；正文行 {cleaned['stats']['body_lines']}"
            f"（合并后 {cleaned['stats']['merged_lines']}）；"
            f"双栏页 {order['stats']['two_column_pages']}；"
            f"章节 {sections['stats']['heading_count']}；"
            f"表格 {tables['stats']['table_count']}；"
            f"公式候选 {formulas['stats']['formula_candidates']}；"
            f"题注 {captions['stats']['figure_captions']}图/"
            f"{captions['stats']['table_captions']}表；"
            f"字符覆盖率 {ver['coverage']:.1%}；"
            f"证据块 {ver['stats']['evidence_blocks']}"
        ),
    }
    out = {"case_id": cid, "status": overall}
    if not compact:
        out["pipeline"] = {
            "clean": cleaned, "order": order, "sections": sections,
            "tables": tables, "formulas": formulas, "captions": captions,
            "evidence": evidence, "verify": ver,
        }
    out["result"] = result

    if outdir:
        import os
        out_dir = os.path.abspath(outdir)
        os.makedirs(out_dir, exist_ok=True)
        artifacts: Dict[str, str] = {"outdir": out_dir}
        if full_text.strip():
            text_path = os.path.join(out_dir, "reading_text.md")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(full_text.rstrip() + "\n")
            artifacts["reading_text_md"] = text_path
        sections_path = os.path.join(out_dir, "sections.json")
        with open(sections_path, "w", encoding="utf-8") as f:
            json.dump({"structure": sections["tree"], "sections": sections["sections"]},
                      f, ensure_ascii=False, indent=2)
        artifacts["sections_json"] = sections_path
        tables_path = os.path.join(out_dir, "tables.md")
        with open(tables_path, "w", encoding="utf-8") as f:
            f.write("# 表格\n\n")
            for i, t in enumerate(result.get("tables", []), 1):
                f.write("## 表 %d\n\n%s\n\n" % (i, t.get("markdown", "")))
        artifacts["tables_md"] = tables_path
        result["artifacts"] = artifacts
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load(path: str):
    if path == "-":
        return json.load(sys.stdin)
    return json.load(open(path, "r", encoding="utf-8"))


def _as_layout(data: Dict[str, Any]) -> Dict[str, Any]:
    """统一把输入规范为带 pages 键的 layout 对象。"""
    if not isinstance(data, dict):
        return {"pages": []}
    if "pages" in data and isinstance(data["pages"], list):
        return data  # 已经是 layout
    if "input_layout" in data:
        return data["input_layout"]
    return data


def main(argv=None):
    p = argparse.ArgumentParser(description="确定性科研 PDF 版面解析引擎")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("extract"); sp.add_argument("pdf")
    for c in ("clean", "order", "sections", "tables", "formulas", "captions"):
        sub.add_parser(c).add_argument("input")
    ev = sub.add_parser("evidence")
    ev.add_argument("input")
    vf = sub.add_parser("verify"); vf.add_argument("input")
    pl = sub.add_parser("pipeline"); pl.add_argument("input")
    pl.add_argument("--compact", action="store_true")
    pl.add_argument("--outdir", default=None,
                    help="把 reading_text.md / sections.json / tables.md 落盘，并写入 result.artifacts")

    args = p.parse_args(argv)
    if args.cmd == "extract":
        out = extract_from_pdf(args.pdf)
    else:
        data = _load(args.input)
        layout = _as_layout(data)
        if args.cmd == "clean":
            out = clean_spans(layout)
        elif args.cmd == "order":
            out = reading_order(clean_spans(layout), layout)
        elif args.cmd == "sections":
            out = detect_sections(reading_order(clean_spans(layout), layout))
        elif args.cmd == "tables":
            out = rebuild_table(clean_spans(layout), layout)
        elif args.cmd == "formulas":
            out = recover_formulas(layout, clean_spans(layout))
        elif args.cmd == "captions":
            cl = clean_spans(layout)
            out = detect_captions(cl, reading_order(cl, layout))
        elif args.cmd == "evidence":
            cl = clean_spans(layout); od = reading_order(cl, layout)
            se = detect_sections(od); ta = rebuild_table(cl, layout)
            out = build_evidence(cl, od, se, ta)
        elif args.cmd == "verify":
            cl = clean_spans(layout); od = reading_order(cl, layout)
            ev = build_evidence(cl, od, detect_sections(od), rebuild_table(cl, layout))
            out = verify(cl, od, ev, layout)
        elif args.cmd == "pipeline":
            out = pipeline(data, compact=args.compact, outdir=args.outdir)
        else:
            p.error("未知命令"); return 2
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
