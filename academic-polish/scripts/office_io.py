#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""office_io.py — 无第三方依赖的 .docx 读写

读：解析 word/document.xml 段落；
写：生成最小可用 docx（标题 + 段落，保留换行），供需要可编辑 Word 产物的案例使用。
说明：不复制原文档样式/批注/修订痕迹；如需保留版式，应在 result 中诚实标注“纯文本重排”。
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional

from case_io import read_docx, read_text_file


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _paragraph_xml(text: str, style: Optional[str] = None) -> str:
    ppr = '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % style if style else ""
    runs = []
    for i, line in enumerate(text.split("\n")):
        if i:
            runs.append("<w:r><w:br/></w:r>")
        runs.append('<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % _escape(line))
    return "<w:p>%s%s</w:p>" % (ppr, "".join(runs))


def write_docx(path: str, paragraphs: Iterable[str], title: Optional[str] = None) -> str:
    body = []
    if title:
        body.append(_paragraph_xml(title, "Title"))
    for para in paragraphs:
        body.append(_paragraph_xml(str(para)))
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>%s<w:sectPr/></w:body></w:document>" % "".join(body)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        "</w:styles>"
    )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", styles)
    return str(p)


def docx_paragraphs(path: str) -> List[str]:
    r = read_docx(Path(path))
    if not r.get("ok"):
        return []
    text = r.get("text", "")
    return [x.strip() for x in re.split(r"\n\s*\n", text) if x.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="docx 读写")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read")
    r.add_argument("path")
    r.add_argument("--out", default=None)
    w = sub.add_parser("write")
    w.add_argument("--input", required=True, help="UTF-8 文本，段落以空行分隔")
    w.add_argument("--out", required=True, help=".docx 输出路径")
    w.add_argument("--title", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "read":
        paras = docx_paragraphs(args.path)
        out = json.dumps({"paragraphs": paras, "count": len(paras)}, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(out, encoding="utf-8")
        print(out)
        return 0
    text = Path(args.input).read_text(encoding="utf-8", errors="replace")
    paras = [x.strip() for x in re.split(r"\n\s*\n", text) if x.strip()]
    print(write_docx(args.out, paras, args.title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
