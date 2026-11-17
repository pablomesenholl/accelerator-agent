"""Report-template and PDF-inspection integration checks; no physics execution."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from PIL import Image
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from compile_report import compile_report
from inspect_report import inspect_report, log_findings
from setup_latex import sha256

FIXTURES = Path(__file__).parent
TEMPLATE = ROOT / "src/skills/scientific-reporting/assets/report-template.tex"


def prepare_report(directory, kind):
    directory.mkdir(parents=True)
    before, rest = TEMPLATE.read_text().split("% BEGIN BODY\n")
    _, after = rest.split("% END BODY\n")
    source = directory / "report.tex"
    source.write_text(before + (FIXTURES / f"{kind}-body.tex").read_text() + after)
    shutil.copy(FIXTURES / "references.bib", directory)
    shutil.copy(ROOT / "src/skills/beam-analyzer/assets/OPALX-logo.png", directory / "figure.png")
    return source


@unittest.skipUnless((ROOT / ".tools/tectonic/installed.json").exists(), "Install compiler first")
class InspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.builds = {}
        for kind in ("particle", "cof"):
            source = prepare_report(cls.root / kind, kind)
            inputs = {p: p.read_bytes() for p in source.parent.iterdir()}
            build = source.parent / "build"
            compile_report(source, build, offline=True)
            assert all(p.read_bytes() == data for p, data in inputs.items())
            cls.builds[kind] = build

    def copy_build(self, name, kind="particle"):
        # build.json contains absolute paths; repoint the copied PDF for isolated failures.
        target = self.root / name
        shutil.copytree(self.builds[kind], target)
        record = json.loads((target / "build.json").read_text())
        record["pdf"] = str(target / "report.pdf")
        (target / "build.json").write_text(json.dumps(record))
        return target

    def test_both_layouts_render_and_ignore_first_pass_warnings(self):
        for kind in self.builds:
            with self.subTest(kind=kind):
                build = self.copy_build(f"render-{kind}", kind)
                # Combined output may contain resolved intermediate-pass messages.
                with (build / "compile.log").open("a") as log:
                    log.write("LaTeX Warning: Reference `old' undefined on input line 1.\n")
                result = inspect_report(build)
                self.assertEqual(result["status"], "completed", result)
                self.assertFalse([f for f in result["findings"] if f["severity"] != "advisory"], result)
                with pdfium.PdfDocument(build / "report.pdf") as pdf:
                    self.assertEqual(result["page_count"], len(pdf))
                self.assertLessEqual(result["page_count"], 3)
                self.assertEqual(len(result["pages"]), result["page_count"])
                for page in result["pages"]:
                    with Image.open(build / "inspection" / page["image"]) as image:
                        self.assertGreater(image.width, 1000)
                    self.assertTrue((build / "inspection" / page["text"]).read_text())
                self.assertEqual(result["visual_review"], "not_performed")
                before = (build / "inspection/inspection.json").read_bytes()
                with self.assertRaises(FileExistsError):
                    inspect_report(build)
                self.assertEqual((build / "inspection/inspection.json").read_bytes(), before)

    def test_actual_unresolved_reference_and_overflow_are_findings(self):
        source = self.root / "warnings.tex"
        source.write_text(r"\documentclass{article}\begin{document}"
                          r"See \ref{missing}.\hbox to 1pt{A deliberately wide box}"
                          r"\end{document}")
        build = self.root / "warnings-build"
        compile_report(source, build, offline=True)
        result = inspect_report(build)
        self.assertEqual(result["status"], "completed", result)
        self.assertIn("unresolved", {f["kind"] for f in result["findings"]})
        self.assertIn("overflow", {f["kind"] for f in result["findings"]})

    def test_corrupt_and_mismatched_pdf_fail_with_record(self):
        for corrupt in (False, True):
            build = self.copy_build(f"bad-pdf-{corrupt}")
            pdf = build / "report.pdf"
            pdf.write_bytes(b"not a PDF")
            if corrupt:
                record = json.loads((build / "build.json").read_text())
                record["pdf_sha256"] = sha256(pdf)
                (build / "build.json").write_text(json.dumps(record))
            result = inspect_report(build)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["errors"])
            self.assertTrue((build / "inspection/inspection.json").is_file())

    def test_missing_logs_are_incomplete(self):
        build = self.copy_build("missing-log")
        (build / "report.blg").unlink()
        result = inspect_report(build)
        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(result["pages"])
        self.assertIn("Missing final log", result["errors"][0])


class DiagnosticTests(unittest.TestCase):
    def test_wrapped_diagnostics_locations_and_severity(self):
        findings = log_findings("LaTeX Warning: Citation `missing' on page 1 undefined on input\nline 42.\n\n"
                                "Overfull \\hbox (12.5pt too wide) in paragraph at lines 8--9\n\n"
                                "Underfull \\hbox (badness 1000) at line 10\n\n"
                                "Warning--I didn't find a database entry for x\n", "report.log")
        self.assertEqual(findings[0]["source_line"], 42)
        overflow = next(f for f in findings if f["kind"] == "overflow")
        self.assertEqual(overflow["overflow_pt"], 12.5)
        self.assertEqual(overflow["source_end_line"], 9)
        self.assertEqual(overflow["severity"], "review")
        self.assertEqual({f["severity"] for f in findings}, {"error", "review", "advisory"})


if __name__ == "__main__":
    unittest.main()
