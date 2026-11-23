#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compile_latex.py — 真实 LaTeX 编译与修复闭环

用途：
  1. 识别工程主文件与 TeX 引擎（magic comment / ctex / xeCJK / 文档类）；
  2. 在临时副本中真实调用 latexmk 或 pdflatex/xelatex/lualatex/tectonic，
     多轮编译直到引用与交叉引用收敛；
  3. 解析 .log，把每条错误定位到文件:行号:根因，区分级联错误；
  4. 复制 PDF 与可编辑源码到输出目录，并核对页数、文件大小；
  5. 输出机器可读 JSON，供 result.json 与人工复核直接引用。

不修改原始工程。只依赖 Python 标准库；编译器由平台镜像提供。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

TEXT_EXT = {".tex", ".bib", ".cls", ".sty", ".bst", ".cfg", ".def", ".ltx", ".txt", ".md"}
COPY_EXT = TEXT_EXT | {".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".csv", ".dat"}
ENGINES = ("latexmk", "pdflatex", "xelatex", "lualatex", "tectonic")


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def available_engines() -> List[str]:
    return [e for e in ENGINES if _which(e)]


def find_main(root: Path, main: Optional[str] = None) -> Optional[Path]:
    if main:
        p = (root / main).resolve()
        if p.is_file() and p.suffix.lower() == ".tex":
            return p
        # 允许只给 stem
        p2 = (root / (main + ".tex")).resolve()
        if p2.is_file():
            return p2
    tex = sorted(root.rglob("*.tex"))
    if not tex:
        return None
    scored = []
    for p in tex:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""
        score = 0
        if "\\documentclass" in text:
            score += 5
        if "\\begin{document}" in text:
            score += 3
        if "\\end{document}" in text:
            score += 1
        scored.append((score, p.stat().st_size, p))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return scored[0][2]


def detect_engine(main_tex: Path, requested: str = "auto") -> str:
    if requested and requested != "auto":
        return requested
    try:
        head = "\n".join(main_tex.read_text(encoding="utf-8", errors="replace").splitlines()[:40])
    except Exception:
        head = ""
    m = re.search(r"%\s*!TEX\s+(?:program|TS-program)\s*=\s*([A-Za-z]+)", head, re.I)
    if m:
        name = m.group(1).lower()
        if name in ("pdflatex", "xelatex", "lualatex", "tectonic"):
            return name
    for token in ("ctex", "xeCJK", "fontspec", "unicode-math"):
        if re.search(r"\\usepackage(\[[^\]]*\])?\{[^}]*%s" % re.escape(token), head):
            return "xelatex"
    if re.search(r"\\documentclass(\[[^\]]*\])?\{[^}]*beamer", head):
        return "pdflatex"
    return "pdflatex"


def _snapshot(project: Path, work: Path) -> None:
    """复制工程到临时目录；跳过 VCS/缓存/旧构建产物。"""
    ignore = shutil.ignore_patterns(
        ".git", ".svn", "__pycache__", "*.aux", "*.log", "*.out", "*.toc",
        "*.fls", "*.fdb_latexmk", "*.synctex.gz", "*.bcf", "*.blg", "*.run.xml",
        "*.nav", "*.snm", "*.vrb", "*.xdv",
    )
    shutil.copytree(project, work, dirs_exist_ok=True, ignore=ignore)


def _run(cmd: List[str], cwd: Path, timeout: int) -> Dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("max_print_line", "1000")
    env.setdefault("error_line", "254")
    env.setdefault("half_error_line", "238")
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            errors="replace", timeout=timeout, env=env,
        )
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout[-6000:],
            "stderr": proc.stderr[-3000:],
            "timeout": False,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": " ".join(cmd),
            "returncode": -9,
            "stdout": (e.stdout or "")[-4000:] if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "")[-2000:] if isinstance(e.stderr, str) else "",
            "timeout": True,
        }
    except FileNotFoundError:
        return {"cmd": " ".join(cmd), "returncode": 127, "stdout": "",
                "stderr": "compiler_not_found", "timeout": False}


def parse_log(log_text: str, root: Path) -> Dict[str, Any]:
    lines = log_text.splitlines()
    errors: List[Dict[str, Any]] = []
    warnings: List[str] = []
    # file-line-error 形式： ./main.tex:12: Undefined control sequence.
    fl = re.compile(r"^(.+?\.(?:tex|sty|cls|bib)):(\d+):\s*(.*)$")
    # 传统形式： ! Undefined control sequence. 然后 l.12
    bang = re.compile(r"^!\s*(.+)$")
    lnum = re.compile(r"^l\.(\d+)\s*(.*)$")

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        m = fl.match(line)
        if m:
            errors.append({
                "file": m.group(1).lstrip("./"),
                "line": int(m.group(2)),
                "message": m.group(3).strip(),
                "raw": line,
            })
            i += 1
            continue
        m = bang.match(line)
        if m:
            msg = m.group(1).strip()
            loc = None
            context = []
            for j in range(i + 1, min(i + 8, len(lines))):
                lm = lnum.match(lines[j].strip())
                if lm:
                    loc = int(lm.group(1))
                    break
            for j in range(max(0, i - 3), i):
                if lines[j].strip():
                    context.append(lines[j].strip())
            errors.append({
                "file": None,
                "line": loc,
                "message": msg,
                "raw": line,
                "context": context[-2:],
            })
            i += 1
            continue
        if re.search(r"^(LaTeX Warning|Package .* Warning|Overfull|Underfull)", line):
            if len(warnings) < 80:
                warnings.append(line[:300])
        i += 1

    # 合并同一 file:line 的重复（多轮编译会重复报）
    seen = set()
    unique = []
    for e in errors:
        key = (e.get("file"), e.get("line"), e.get("message"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)

    # 级联判定：同一文件相邻 10 行内 3 条以上错误，或错误信息含 runaway argument
    cascading = False
    by_file: Dict[str, List[int]] = {}
    for e in unique:
        if e.get("file") and isinstance(e.get("line"), int):
            by_file.setdefault(e["file"], []).append(e["line"])
    for ls in by_file.values():
        ls.sort()
        for a, b, c in zip(ls, ls[1:], ls[2:]):
            if c - a <= 10:
                cascading = True
                break
    if any("runaway argument" in (e.get("message") or "").lower() for e in unique):
        cascading = True

    missing = []
    for w in warnings:
        m = re.search(r"File [`']([^']+)' not found", w) or re.search(r"Package .* Error: .* not found", w)
        if m:
            missing.append(m.group(1))
    return {"errors": unique, "warnings": warnings, "error_count": len(unique),
            "cascading": cascading, "missing_files": sorted(set(missing))}


def pdf_pages(pdf: Path) -> Optional[int]:
    try:
        from pypdf import PdfReader  # type: ignore
        return len(PdfReader(str(pdf)).pages)
    except Exception:
        pass
    try:
        import fitz  # type: ignore
        return fitz.open(str(pdf)).page_count
    except Exception:
        pass
    if _which("pdfinfo"):
        try:
            out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True,
                                 errors="replace", timeout=20).stdout
            m = re.search(r"^Pages:\s+(\d+)", out, re.M)
            if m:
                return int(m.group(1))
        except Exception:
            pass
    try:
        data = pdf.read_bytes()
        return max(1, len(re.findall(rb"/Type\s*/Page[^s]", data)))
    except Exception:
        return None


def compile_project(project: str, main_tex: Optional[str] = None, engine: str = "auto",
                    outdir: Optional[str] = None, timeout: int = 240,
                    rounds: int = 3, keep_workdir: bool = False) -> Dict[str, Any]:
    root = Path(project).resolve()
    if not root.is_dir():
        return {"status": "error", "reason": "project_not_found", "project": str(root)}
    out = Path(outdir).resolve() if outdir else None
    if out:
        out.mkdir(parents=True, exist_ok=True)

    main_src = find_main(root, main_tex)
    if not main_src:
        return {"status": "error", "reason": "main_tex_not_found", "project": str(root)}

    eng = detect_engine(main_src, engine)
    avail = available_engines()
    if not avail:
        return {
            "status": "error", "reason": "no_latex_compiler",
            "project": str(root), "main_tex": str(main_src),
            "detail": "未找到 latexmk/pdflatex/xelatex/lualatex/tectonic；请先在环境安装 TeX，或如实交付 partial 并说明。",
            "available_engines": [],
        }

    work = Path(tempfile.mkdtemp(prefix="latex_build_"))
    _snapshot(root, work)
    main_rel = main_src.relative_to(root)
    main_work = work / main_rel

    runs: List[Dict[str, Any]] = []
    chosen = None
    if _which("latexmk"):
        flag = {"pdflatex": "-pdf", "xelatex": "-xelatex", "lualatex": "-lualatex",
                "tectonic": "-pdf"}.get(eng, "-pdf")
        cmd = ["latexmk", flag, "-interaction=nonstopmode", "-file-line-error",
               "-halt-on-error", "-synctex=0", main_rel.name]
        runs.append(_run(cmd, work, timeout))
        chosen = "latexmk"
    else:
        exe = _which(eng) or _which("pdflatex")
        if not exe:
            exe = _which("xelatex") or _which("lualatex") or _which("tectonic")
            eng = Path(exe).name if exe else eng
        if exe:
            for r in range(1, rounds + 1):
                cmd = [exe, "-interaction=nonstopmode", "-file-line-error",
                       "-halt-on-error", main_rel.name]
                runs.append(_run(cmd, work, timeout))
                chosen = Path(exe).name
                # 只要已产出 PDF 且上一轮没有 undefined refs，就不再多跑
                log_path = main_work.with_suffix(".log")
                if log_path.exists():
                    txt = log_path.read_text(encoding="utf-8", errors="replace")
                    if "Rerun to get" not in txt and "undefined references" not in txt.lower():
                        break

    stem = main_work.with_suffix("")
    log_path = stem.with_suffix(".log")
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    parsed = parse_log(log_text, root)

    pdf_work = None
    for cand in (stem.with_suffix(".pdf"), work / (main_rel.stem + ".pdf")):
        if cand.exists() and cand.stat().st_size > 0:
            pdf_work = cand
            break

    compile_ok = pdf_work is not None and parsed["error_count"] == 0
    pages = pdf_pages(pdf_work) if pdf_work else None

    delivered_pdf = None
    delivered_src = None
    if out:
        if pdf_work:
            delivered_pdf = out / (main_rel.stem + ".pdf")
            shutil.copy2(pdf_work, delivered_pdf)
        src_dir = out / "latex_source"
        if src_dir.exists():
            shutil.rmtree(src_dir)
        src_dir.mkdir(parents=True, exist_ok=True)
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in COPY_EXT:
                rel = p.relative_to(root)
                dst = src_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
        delivered_src = src_dir

    result = {
        "status": "ok" if compile_ok else ("partial" if pdf_work else "error"),
        "compile_ok": compile_ok,
        "engine": chosen or eng,
        "engine_requested": engine,
        "available_engines": avail,
        "project": str(root),
        "main_tex": str(main_rel),
        "runs": runs,
        "rounds": len(runs),
        "pdf": str(delivered_pdf) if delivered_pdf else None,
        "pdf_bytes": delivered_pdf.stat().st_size if delivered_pdf else 0,
        "pages": pages,
        "source_dir": str(delivered_src) if delivered_src else None,
        "errors": parsed["errors"],
        "error_count": parsed["error_count"],
        "warnings": parsed["warnings"],
        "warning_count": len(parsed["warnings"]),
        "cascading": parsed["cascading"],
        "missing_files": parsed["missing_files"],
        "log_tail": "\n".join(log_text.splitlines()[-40:]),
    }
    if keep_workdir:
        result["workdir"] = str(work)
    else:
        shutil.rmtree(work, ignore_errors=True)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="真实 LaTeX 编译与修复闭环")
    ap.add_argument("project", help="LaTeX 工程目录")
    ap.add_argument("--main", default=None, help="主文件（相对路径或文件名，可省略）")
    ap.add_argument("--engine", default="auto",
                    choices=["auto", "latexmk", "pdflatex", "xelatex", "lualatex", "tectonic"])
    ap.add_argument("--outdir", default=None, help="交付目录：复制 PDF 与可编辑源码")
    ap.add_argument("--timeout", type=int, default=240, help="单轮编译秒数")
    ap.add_argument("--rounds", type=int, default=3, help="无 latexmk 时的最大轮数")
    ap.add_argument("--keep-workdir", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    res = compile_project(args.project, args.main, args.engine, args.outdir,
                          args.timeout, args.rounds, args.keep_workdir)
    text = json.dumps(res, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    print(text)
    # exit 0 表示脚本执行成功；编译是否成功看 compile_ok，避免把“编译失败”误判成脚本失败
    return 0


if __name__ == "__main__":
    sys.exit(main())
