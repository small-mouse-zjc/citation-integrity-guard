#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""case_io.py — 读取平台 case.json 与常见输入文件

纯标准库。支持：
  - .json：递归收集文本字段与文件路径
  - .txt / .md / .tex / .csv
  - .docx：读取 word/document.xml 的段落（无需 python-docx）
  - .pdf：优先 pdftotext，其次 PyMuPDF；都没有时返回错误说明

用途：让 Agent 不必为“case 里到底是 txt/docx/pdf”反复试错。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TEXT_SUFFIX = {".txt", ".md", ".markdown", ".tex", ".csv", ".json", ".yaml", ".yml"}
DOC_SUFFIX = {".docx", ".pdf", ".doc"}


def read_text_file(path: Path) -> Dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIX:
        try:
            return {"ok": True, "text": path.read_text(encoding="utf-8", errors="replace")}
        except Exception as e:
            return {"ok": False, "error": str(e), "text": ""}
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix == ".doc":
        return {"ok": False, "error": "legacy_doc_unsupported", "text": ""}
    try:
        return {"ok": True, "text": path.read_text(encoding="utf-8", errors="replace")}
    except Exception:
        return {"ok": False, "error": "binary_or_unsupported", "text": ""}


def read_docx(path: Path) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception as e:
        return {"ok": False, "error": "docx_open_failed: %s" % e, "text": ""}
    xml = xml.replace("</w:p>", "\n\n")
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
    # 只保留文本节点
    parts = re.findall(r"<w:t[^>]*>(.*?)</w:t>|(\n)", xml, re.S)
    out = []
    for a, b in parts:
        if b:
            out.append("\n")
        elif a:
            out.append(_unescape_xml(a))
    text = "".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return {"ok": True, "text": text, "format": "docx"}


def _unescape_xml(s: str) -> str:
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            .replace("&apos;", "'").replace("&amp;", "&"))


def read_pdf(path: Path) -> Dict[str, Any]:
    if shutil.which("pdftotext"):
        try:
            proc = subprocess.run(
                ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
                capture_output=True, text=True, errors="replace", timeout=120,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return {"ok": True, "text": proc.stdout, "format": "pdf", "backend": "pdftotext"}
            err = (proc.stderr or "")[-500:]
        except Exception as e:
            err = str(e)
    else:
        err = "pdftotext_not_found"
    try:
        import fitz  # type: ignore
        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        text = "\n".join(pages)
        if text.strip():
            return {"ok": True, "text": text, "format": "pdf", "backend": "pymupdf"}
    except Exception as e:
        err = "%s; pymupdf: %s" % (err, e)
    return {"ok": False, "error": "pdf_text_unavailable: %s" % err, "text": ""}


def _walk_values(obj: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_values(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_values(v, f"{prefix}[{i}]" if prefix else f"[{i}]")
    else:
        yield prefix, obj


def load_case(path: str) -> Dict[str, Any]:
    p = Path(path).resolve()
    if p.is_dir():
        for name in ("case.json", "input.json", "task.json"):
            cand = p / name
            if cand.exists():
                return load_case(str(cand))
        return {"_case_dir": str(p), "_raw": ""}
    if p.suffix.lower() == ".json":
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            return {"_error": "json_parse_failed: %s" % e, "_path": str(p)}
        if isinstance(data, dict):
            data.setdefault("_case_path", str(p))
        return data
    text = p.read_text(encoding="utf-8", errors="replace")
    return {"_path": str(p), "text": text}


def collect_texts(case: Any, base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """递归收集 case 中的文本与可读文件；返回 {items: [{key,text,source,format}], errors}。"""
    base = Path(base_dir).resolve() if base_dir else None
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    def add(key: str, text: str, source: str, fmt: str = "text"):
        if text and text.strip():
            items.append({"key": key, "text": text, "source": source, "format": fmt})

    def visit(obj: Any, key: str):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k).startswith("_"):
                    continue
                visit(v, f"{key}.{k}" if key else str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                visit(v, f"{key}[{i}]")
        elif isinstance(obj, str):
            s = obj.strip()
            # 绝对/相对路径：存在且后缀可读则读取
            if base and s and len(s) < 500 and "\n" not in s and re.search(r"\.(txt|md|tex|docx|pdf|csv)$", s, re.I):
                cand = (base / s) if not os.path.isabs(s) else Path(s)
                if cand.exists() and cand.is_file():
                    r = read_text_file(cand)
                    if r.get("ok"):
                        add(key, r["text"], str(cand), r.get("format", "file"))
                    else:
                        errors.append({"key": key, "path": str(cand), "error": r.get("error")})
                    return
            # 长文本或显式 text 字段
            if len(s) > 40 or key.lower().endswith(("text", "content", "source", "manuscript", "draft", "paragraph")):
                add(key, obj, key, "text")
        else:
            return

    if isinstance(case, dict):
        # 先从文件路径字段读取，避免把路径本身当正文
        for k, v in case.items():
            if isinstance(v, str) and re.search(r"\.(pdf|docx|txt|md)$", v, re.I):
                visit(v, str(k))
        for k, v in case.items():
            if k in ("_case_path", "_path"):
                continue
            visit(v, str(k))
    elif isinstance(case, str):
        add("text", case, "raw", "text")
    return {"items": items, "errors": errors}


def output_contract(case: Dict[str, Any]) -> Dict[str, Any]:
    """尽量从 case.json 提取 output_contract / required_fields。"""
    fields: List[str] = []
    raw = None
    for key in ("output_contract", "outputContract", "required_fields", "expected_fields"):
        if isinstance(case, dict) and key in case:
            raw = case[key]
            break
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict) and "required" in v and not v.get("required"):
                continue
            fields.append(str(k))
    elif isinstance(raw, list):
        for x in raw:
            if isinstance(x, str):
                fields.append(x)
            elif isinstance(x, dict):
                name = x.get("name") or x.get("field") or x.get("key")
                if name:
                    fields.append(str(name))
    elif isinstance(raw, str):
        fields = re.findall(r"`([A-Za-z_][A-Za-z0-9_.-]{1,60})`", raw)
    # 去重保序
    seen = set()
    fields = [f for f in fields if not (f in seen or seen.add(f))]
    return {"raw": raw, "fields": fields}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="读取 case.json 与输入文件")
    ap.add_argument("case", help="case.json 或输入目录")
    ap.add_argument("--out", default=None, help="输出 JSON")
    ap.add_argument("--dump-text", default=None, help="把抽取到的正文合并写成纯文本，供 polish_audit 使用")
    ap.add_argument("--base-dir", default=None)
    args = ap.parse_args(argv)
    case = load_case(args.case)
    base = Path(args.base_dir) if args.base_dir else Path(args.case).resolve().parent
    texts = collect_texts(case, base)
    if args.dump_text:
        items = texts.get("items", []) if isinstance(texts, dict) else []
        body = "\n\n".join(str(it.get("text", "")).strip()
                           for it in items if str(it.get("text", "")).strip())
        if body:
            Path(args.dump_text).parent.mkdir(parents=True, exist_ok=True)
            Path(args.dump_text).write_text(body + "\n", encoding="utf-8")
    out = {"case_path": args.case, "contract": output_contract(case), "texts": texts}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
