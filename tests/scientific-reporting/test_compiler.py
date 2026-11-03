"""Offline integration checks; first warm the cache as described in README.md."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name("report.tex")
COMPILER = ROOT / "scripts" / "compile_report.py"
PYTHON = ROOT / ".venv" / "bin" / "python"


@unittest.skipUnless((ROOT / ".tools/tectonic/installed.json").exists(), "Install the toolchain first")
class CompilerTests(unittest.TestCase):
    def run_compiler(self, source, outdir):
        return subprocess.run(
            [str(PYTHON), str(COMPILER), str(source), "--outdir", str(outdir), "--offline"],
            capture_output=True, text=True, timeout=660,
        )

    def test_report_and_preserved_build(self):
        before = FIXTURE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            outdir = Path(temporary) / "build with spaces"
            result = self.run_compiler(FIXTURE, outdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            pdf = outdir / "report.pdf"
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
            self.assertEqual(json.loads((outdir / "build.json").read_text())["status"], "completed")
            self.assertIn("Courant", (outdir / "report.bbl").read_text())
            final_log = (outdir / "report.log").read_text()
            self.assertNotIn("undefined", final_log.lower())
            self.assertNotIn("Overfull", final_log)
            old_pdf = pdf.read_bytes()
            self.assertNotEqual(self.run_compiler(FIXTURE, outdir).returncode, 0)
            self.assertEqual(pdf.read_bytes(), old_pdf)
        self.assertEqual(FIXTURE.read_bytes(), before)

    def test_invalid_tex_retains_failure_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "broken.tex"
            source.write_text(r"\documentclass{article}\begin{document}\undefinedcommand\end{document}")
            outdir = Path(temporary) / "build"
            result = self.run_compiler(source, outdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads((outdir / "build.json").read_text())["status"], "failed")
            self.assertIn("Undefined control sequence", (outdir / "compile.log").read_text())
            self.assertFalse((outdir / "broken.pdf").exists())

    def test_uncached_package_fails_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "missing.tex"
            source.write_text(r"\documentclass{article}\usepackage{accelerator-nonexistent-test-package}"
                              r"\begin{document}Test\end{document}")
            outdir = Path(temporary) / "build"
            result = self.run_compiler(source, outdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads((outdir / "build.json").read_text())["status"], "failed")
            self.assertFalse((outdir / "missing.pdf").exists())


if __name__ == "__main__":
    unittest.main()
