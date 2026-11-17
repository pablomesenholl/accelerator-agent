"""Inspect a completed report build and render pages; does not certify visual review."""

import argparse
from importlib.metadata import version
import json
from pathlib import Path
import re

import pypdfium2 as pdfium

from setup_latex import sha256


def log_findings(text, path):
    """Classify final-pass diagnostics, including wrapped LaTeX warning lines."""
    findings = []
    patterns = (
        ("unresolved", "error", r"LaTeX Warning: (?:Reference|Citation)\b.*?undefined[^\n]*"),
        ("unresolved", "error", r"LaTeX Warning: There were undefined (?:references|citations)\.?"),
        ("bibliography", "error", r"Warning--[^\n]*|I couldn't open[^\n]*|I found no[^\n]*"),
        ("overflow", "review", r"Overfull \\[hv]box[^\n]*"),
        ("formatting", "advisory", r"Underfull \\[hv]box[^\n]*|LaTeX Warning: `[^\n]*float[^\n]*"),
    )
    # TeX wraps warnings at its output width. Preserve paragraph boundaries.
    normalized = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    for kind, severity, pattern in patterns:
        for match in re.finditer(pattern, normalized):
            message = match.group().strip()
            # Stop at subsequent diagnostics in the same paragraph.
            message = re.split(r" (?=LaTeX Warning:|Overfull|Underfull)", message)[0]
            finding = {"kind": kind, "severity": severity, "message": message,
                       "log": str(path)}
            location = re.search(r"(?:at lines?|at line|input line)\s+(\d+)(?:--(\d+))?", message)
            if location:
                finding["source_line"] = int(location[1])
                if location[2]:
                    finding["source_end_line"] = int(location[2])
            width = re.search(r"\(([\d.]+)pt too (wide|high)\)", message)
            if width:
                finding["overflow_pt"] = float(width[1])
            findings.append(finding)
    return findings


def inspect_report(build_dir, dpi=150):
    if not 36 <= dpi <= 600:
        raise ValueError("DPI must be between 36 and 600")
    build_dir = Path(build_dir).resolve(strict=True)
    build = json.loads((build_dir / "build.json").read_text())
    if build.get("status") != "completed":
        raise ValueError("Expected a completed report build")
    outdir = build_dir / "inspection"
    outdir.mkdir(exist_ok=False)
    record = {"status": "failed", "pdf": build.get("pdf"),
              "pdf_sha256": build.get("pdf_sha256"), "dpi": dpi,
              "renderer": "pypdfium2", "renderer_version": version("pypdfium2"),
              "pages": [], "findings": [], "errors": [],
              "content_review": "not_performed", "visual_review": "not_performed"}
    try:
        pdf_path = Path(build["pdf"])
        if sha256(pdf_path) != build["pdf_sha256"]:
            raise ValueError("PDF hash differs from build.json")
        with pdfium.PdfDocument(pdf_path) as pdf:
            record["page_count"] = len(pdf)
            if not len(pdf):
                raise ValueError("PDF has no pages")
            for index in range(len(pdf)):
                stem = f"page-{index + 1:03d}"
                page = pdf[index]
                try:
                    textpage = page.get_textpage()
                    try:
                        (outdir / f"{stem}.txt").write_text(textpage.get_text_bounded(), encoding="utf-8")
                    finally:
                        textpage.close()
                    bitmap = page.render(scale=dpi / 72)
                    try:
                        with bitmap.to_pil() as image:
                            image.save(outdir / f"{stem}.png")
                    finally:
                        bitmap.close()
                    record["pages"].append({"page": index + 1,
                                            "width_pt": page.get_width(), "height_pt": page.get_height(),
                                            "image": f"{stem}.png", "text": f"{stem}.txt"})
                finally:
                    page.close()
        source = Path(build["source"])
        tex_log = build_dir / source.with_suffix(".log").name
        aux = build_dir / source.with_suffix(".aux").name
        bib_log = build_dir / source.with_suffix(".blg").name
        logs = [tex_log]
        if not aux.is_file():
            record["errors"].append(f"Missing auxiliary file; bibliography check incomplete: {aux}")
        elif "\\bibdata" in aux.read_text(errors="replace") or bib_log.exists():
            logs.append(bib_log)
        for path in logs:
            if not path.is_file():
                record["errors"].append(f"Missing final log: {path}")
            else:
                record["findings"].extend(log_findings(path.read_text(errors="replace"), path))
        record["status"] = "incomplete" if record["errors"] else "completed"
    except Exception as error:
        record["errors"].append(str(error))
    finally:
        (outdir / "inspection.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    try:
        record = inspect_report(args.build_dir, args.dpi)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(record, indent=2))
    if record["status"] != "completed":
        parser.exit(1)


if __name__ == "__main__":
    main()
