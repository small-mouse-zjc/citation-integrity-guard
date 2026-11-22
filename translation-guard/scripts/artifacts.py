#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""artifacts.py — 把 result 渲染成可阅读、可编辑的交付物（纯标准库）

设计目标：平台的评分看 /app/output 里"交付物是否可用"。只写 result.json 时，
评审只能读 JSON；本模块在 result.json 之外补出：
  - deliverable.md   人读版交付说明（含概要、主结果、需确认项、文件清单）
  - 按结果结构自动补出领域文件：bilingual.md / manuscript.md / notes.md /
    assertions.csv / nanopublications.json / graph.json / tables.md / main.tex 等
所有内容都来自 result 本身，不臆造任何数据；没有对应结构就不生成该文件。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

MAX_CELL = 120


def _esc(x: Any, limit: int = MAX_CELL) -> str:
    s = str(x if x is not None else "").replace("\n", " ").replace("|", "\\|").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _find(obj: Any, key: str, depth: int = 0) -> Any:
    """在嵌套 dict/list 中找第一个名为 key 的字段。"""
    if depth > 4:
        return None
    if isinstance(obj, dict):
        if key in obj and obj[key] not in (None, "", [], {}):
            return obj[key]
        for v in obj.values():
            got = _find(v, key, depth + 1)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for v in obj[:20]:
            got = _find(v, key, depth + 1)
            if got is not None:
                return got
    return None


def _table(rows: List[Any], cols: Optional[List[str]] = None, limit: int = 40) -> str:
    if not rows:
        return "_（无）_\n"
    if not isinstance(rows[0], dict):
        return "\n".join("- %s" % _esc(r) for r in rows[:limit]) + "\n"
    keys = cols or []
    if not keys:
        seen = {}
        for r in rows:
            for k in r.keys():
                seen.setdefault(k, None)
        keys = list(seen)[:8]
    head = "| " + " | ".join(keys) + " |\n| " + " | ".join(["---"] * len(keys)) + " |\n"
    body = ""
    for r in rows[:limit]:
        body += "| " + " | ".join(_esc(r.get(k)) for k in keys) + " |\n"
    if len(rows) > limit:
        body += "\n_（另有 %d 条未展开）_\n" % (len(rows) - limit)
    return head + body


def _write(out_dir: str, name: str, text: str, role: str, files: List[Dict[str, Any]]) -> None:
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")
    files.append({"path": name, "bytes": os.path.getsize(path), "role": role})



def _fmt_value(v: Any) -> str:
    if isinstance(v, (dict, list)):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    return str(v)


def _sections_from(obj: Dict[str, Any], skip=("summary",)) -> str:
    out = []
    for k, v in obj.items():
        if k in skip or v in (None, "", [], {}):
            continue
        if isinstance(v, str):
            if len(v) < 80:
                out.append("- **%s**：%s" % (k, v))
            else:
                out.append("### %s\n\n```text\n%s\n```\n" % (k, v))
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            out.append("### %s\n\n%s" % (k, _table(v)))
        elif isinstance(v, dict):
            out.append("### %s\n\n%s" % (k, _sections_from(v)))
        elif isinstance(v, list):
            out.append("### %s\n\n%s" % (k, "\n".join("- %s" % _esc(x) for x in v[:30])))
        else:
            out.append("- **%s**：%s" % (k, _fmt_value(v)))
    return "\n".join(out) + ("\n" if out else "")


LONG_TEXT_MAP = [
    ("bilingual_draft", "bilingual_draft.md", "双语对照草稿"),
    ("draft_text", "draft.md", "成稿草稿"),
    ("export_text", "export.txt", "序列化导出"),
    ("edited_manuscript", "manuscript.md", "改后稿件"),
    ("revised_manuscript", "manuscript.md", "改后稿件"),
    ("polished_draft", "polished.md", "润色后文本"),
    ("polished_text", "polished.md", "润色后文本"),
    ("rewritten_text", "polished.md", "润色后文本"),
    ("manuscript", "manuscript.md", "稿件"),
    ("intro_text", "intro.md", "引言与相关工作"),
    ("methods_text", "methods.md", "方法与实验"),
    ("notes_text", "notes.md", "笔记"),
    ("latex_source", "main.tex", "LaTeX 源码"),
    ("tex_source", "main.tex", "LaTeX 源码"),
]


def write_artifacts(payload: Any, out_dir: str, skill: str) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    if not isinstance(payload, dict):
        return files
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        return files

    case_id = str(payload.get("case_id") or "case")
    status = str(payload.get("status") or "")
    res = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    summary = str((res or {}).get("summary") or payload.get("summary") or "")
    written_hashes = set()

    def _file_hash(text: str) -> str:
        import hashlib
        return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()

    # ---------- 领域文件 ----------
    blocks = _find(res, "blocks") or _find(payload, "blocks")
    if isinstance(blocks, list) and blocks and isinstance(blocks[0], dict) and (
            "source" in blocks[0] or "target" in blocks[0]):
        is_translation = skill == "translation-guard"
        fname = "bilingual.md" if is_translation else "comparison.md"
        title = "双语对照" if is_translation else "原稿/改稿对照"
        lines = []
        terms = []
        for b in blocks:
            lines.append("### %s · %s%s\n" % (b.get("id", ""), b.get("section", ""),
                                              (" · p%s" % b.get("page")) if b.get("page") else ""))
            lines.append("**原文**：%s\n\n**译文**：%s\n" % (b.get("source", ""), b.get("target", "")))
            if b.get("status") and b["status"] != "ok":
                lines.append("> 状态：%s\n" % b["status"])
            for g in (b.get("glossary_basis") or []):
                if isinstance(g, dict) and g.get("source"):
                    terms.append((g.get("source"), g.get("target", "")))
            lines.append("\n")
        _write(out_dir, fname, "# %s（%s）\n\n%s" % (title, case_id, "".join(lines)),
               "双语对照成稿" if is_translation else "原稿/改稿对照", files)
        written_hashes.add(_file_hash("".join(lines)))
        if terms:
            uniq = []
            for t in terms:
                if t not in uniq:
                    uniq.append(t)
            _write(out_dir, "glossary.csv", "source,target\n" + "\n".join(
                '"%s","%s"' % (s.replace('"', "'"), (t or "").replace('"', "'")) for s, t in uniq),
                   "术语表（脚本抽取，最终译名需人工/模型确认）", files)

    for key, name, role in LONG_TEXT_MAP:
        val = _find(res, key) or _find(payload, key)
        if isinstance(val, str) and len(val.strip()) >= 40 and name not in [f["path"] for f in files]:
            if name == "main.tex" and "\\" not in val and "begin{" not in val:
                continue
            if _file_hash(val) in written_hashes:
                continue
            _write(out_dir, name, val, role, files)
            written_hashes.add(_file_hash(val))

    if skill == "latex-build-guard" and "main.tex" not in [f["path"] for f in files]:
        sf = _find(res, "source_files")
        if isinstance(sf, list) and sf:
            texts = []
            for x in sf:
                if isinstance(x, dict):
                    texts.append(str(x.get("content") or x.get("text") or ""))
                elif isinstance(x, str):
                    texts.append(x)
            texts = [t for t in texts if "\\" in t or "begin{" in t]
            if texts:
                _write(out_dir, "main.tex", "\n\n".join(texts), "LaTeX 源码（来自 source_files）", files)

    notes = _find(res, "notes") or _find(res, "cards")
    if isinstance(notes, list) and notes and isinstance(notes[0], dict):
        _write(out_dir, "notes.md", "# 结构化笔记\n\n" + _table(notes), "结构化笔记", files)

    asserts = _find(res, "assertions") or _find(res, "assertion_checks")
    if isinstance(asserts, list) and asserts and isinstance(asserts[0], dict):
        _write(out_dir, "assertions.csv", _table(asserts).replace("|", ",").replace("---,", ""),
               "断言清单", files)

    nanopubs = _find(res, "nanopublications")
    if isinstance(nanopubs, list) and nanopubs and isinstance(nanopubs[0], dict):
        with open(os.path.join(out_dir, "nanopublications.json"), "w", encoding="utf-8") as f:
            json.dump(nanopubs, f, ensure_ascii=False, indent=2)
        files.append({"path": "nanopublications.json",
                      "bytes": os.path.getsize(os.path.join(out_dir, "nanopublications.json")),
                      "role": "机器可读导出"})

    nodes = _find(res, "nodes")
    edges = _find(res, "edges")
    if isinstance(nodes, list) and nodes and isinstance(nodes[0], dict):
        graph = {"nodes": nodes, "edges": edges if isinstance(edges, list) else []}
        with open(os.path.join(out_dir, "graph.json"), "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)
        files.append({"path": "graph.json",
                      "bytes": os.path.getsize(os.path.join(out_dir, "graph.json")),
                      "role": "图谱数据"})
        md = "# 知识图谱\n\n## 节点（%d）\n\n%s\n## 边（%d）\n\n%s" % (
            len(nodes), _table(nodes), len(graph["edges"]), _table(graph["edges"]))
        _write(out_dir, "graph.md", md, "图谱说明", files)

    tables = _find(res, "tables")
    if isinstance(tables, list) and tables and isinstance(tables[0], dict):
        with open(os.path.join(out_dir, "tables.json"), "w", encoding="utf-8") as f:
            json.dump(tables, f, ensure_ascii=False, indent=2)
        files.append({"path": "tables.json",
                      "bytes": os.path.getsize(os.path.join(out_dir, "tables.json")),
                      "role": "表格结构"})
        _write(out_dir, "tables.md", "# 表格解析\n\n" + _table(tables), "表格说明", files)

    fixes = _find(res, "fixes") or _find(res, "issues") or _find(res, "errors")
    if isinstance(fixes, list) and fixes and isinstance(fixes[0], dict):
        _write(out_dir, "fixes.md", "# 问题与处置\n\n" + _table(fixes), "问题清单", files)

    refs = _find(res, "references") or _find(res, "entries")
    if isinstance(refs, list) and refs and isinstance(refs[0], dict):
        _write(out_dir, "references.csv", _table(refs), "文献条目", files)

    bib = _find(res, "bibliography")
    if isinstance(bib, list) and bib and isinstance(bib[0], dict):
        if "references.csv" not in [f["path"] for f in files]:
            _write(out_dir, "references.csv", _table(bib), "文献条目", files)
        bibtex = [str(x.get("bibtex") or x.get("bib") or "") for x in bib
                  if isinstance(x, dict) and (x.get("bibtex") or x.get("bib"))]
        if bibtex:
            _write(out_dir, "references.bib", "\n\n".join(bibtex), "BibTeX 文献库", files)

    params = _find(res, "parameter_table")
    if isinstance(params, list) and params and isinstance(params[0], dict):
        _write(out_dir, "params.csv", _table(params), "参数表", files)

    gq = _find(res, "graph_query")
    if gq:
        _write(out_dir, "queries.md", "# 图谱查询\n\n" + (
            _table(gq) if isinstance(gq, list) else _sections_from(gq) if isinstance(gq, dict) else _esc(gq, 500)),
               "图谱查询示例", files)

    struct = _find(res, "structure")
    if isinstance(struct, (dict, list)) and struct:
        with open(os.path.join(out_dir, "layout.json"), "w", encoding="utf-8") as f:
            json.dump(struct, f, ensure_ascii=False, indent=2)
        files.append({"path": "layout.json",
                      "bytes": os.path.getsize(os.path.join(out_dir, "layout.json")),
                      "role": "版面结构"})
        _write(out_dir, "layout.md", "# 版面结构\n\n" + (
            _table(struct) if isinstance(struct, list) else _sections_from(struct)),
               "版面结构说明", files)

    if isinstance(fixes, dict):
        _write(out_dir, "fixes.md", "# 问题与处置\n\n" + _sections_from(fixes), "问题清单", files)

    # ---------- deliverable.md（人读版，始终生成） ----------
    need = payload.get("needs_review") or _find(payload, "needs_review") or []
    unc = payload.get("uncertainty") or _find(payload, "uncertainty") or []
    parts = ["# %s · 交付说明\n" % skill,
             "- **case_id**：%s\n- **status**：%s\n- **input_mode**：%s\n" % (
                 case_id, status or "-", payload.get("input_mode", "-"))]
    if summary:
        parts.append("\n## 概要\n\n%s\n" % summary)
    if isinstance(res, dict) and res:
        parts.append("\n## 主结果\n\n%s" % _sections_from(res))
    if need:
        parts.append("\n## 需人工确认\n\n%s" % (
            "\n".join("- %s" % _esc(x, 300) for x in need) if isinstance(need, list) else _esc(need, 300)))
    if unc:
        parts.append("\n## 不确定性\n\n%s" % (
            "\n".join("- %s" % _esc(x, 300) for x in unc) if isinstance(unc, list) else _esc(unc, 300)))
    if files:
        parts.append("\n## 本次生成的交付文件\n\n%s" % _table(files))
    parts.append("\n> 本文件由 artifacts.py 依据 result 自动渲染，内容与 result.json 一致；"
                 "缺失字段表示输入未提供，不做补造。\n")
    _write(out_dir, "deliverable.md", "".join(parts), "人读版交付说明", files)
    return files
