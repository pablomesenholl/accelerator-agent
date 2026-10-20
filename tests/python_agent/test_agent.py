"""Offline confinement checks and an explicitly enabled live Ollama smoke test."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python-agent"))
from tools.file_tools import WorkspaceFiles


class FileToolsTest(unittest.TestCase):
    def test_file_round_trip_and_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            files = WorkspaceFiles(Path(directory))
            self.assertEqual(files.write_file("notes/task.txt", "hello"), {"written": "notes/task.txt"})
            self.assertEqual(files.edit_file("notes/task.txt", "hello", "done"), {"edited": "notes/task.txt"})
            self.assertEqual(files.read_file("notes/task.txt"), {"content": "done"})
            self.assertEqual(files.list_files("notes"), {"entries": ["task.txt"]})
            self.assertIn("error", files.edit_file("notes/task.txt", "missing", "x"))

    def test_escape_paths_and_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "workspace"
            files = WorkspaceFiles(root)
            outside = base / "outside.txt"
            outside.write_text("preserve")
            (root / "link").symlink_to(base, target_is_directory=True)
            (root / "hardlink").hardlink_to(outside)
            for path in ["../outside.txt", str(outside), "link/outside.txt", "hardlink"]:
                with self.subTest(path=path):
                    self.assertIn("error", files.write_file(path, "changed"))
                    self.assertIn("error", files.read_file(path))
                    self.assertIn("error", files.edit_file(path, "preserve", "changed"))
            self.assertEqual(outside.read_text(), "preserve")


@unittest.skipUnless(os.getenv("RUN_OLLAMA_SMOKE") == "1", "set RUN_OLLAMA_SMOKE=1 for live model test")
class OllamaSmokeTest(unittest.TestCase):
    def test_model_invokes_file_tools(self):
        from agent import run_task
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = asyncio.run(run_task(
                "Use write_file to create smoke.txt containing exactly TOOL_OK. "
                "Then use read_file to read smoke.txt and report its contents.", root,
            ))
            self.assertEqual((root / "smoke.txt").read_text(), "TOOL_OK")
            self.assertIn("write_file", result.tool_calls)
            self.assertIn("read_file", result.tool_calls)
            self.assertTrue(any(
                item["name"] == "read_file" and item["response"].get("content") == "TOOL_OK"
                for item in result.tool_results
            ))
            self.assertTrue(result.response)


if __name__ == "__main__":
    unittest.main()
