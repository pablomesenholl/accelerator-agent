"""Read-only skill discovery and bounded documentation retrieval."""
from pathlib import Path
import re

DEFAULT_SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src" / "skills"
MAX_DOCUMENT_CHARS = 6000
MAX_LINES = 120
MAX_INSTRUCTION_CHARS = 32000


def _metadata(text: str) -> dict:
    """Read the name/description subset of skill frontmatter without a YAML dependency.

    Supports plain/quoted scalars and indented folded/literal descriptions.
    Other metadata fields are intentionally ignored.
    """
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md must start with frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("Unterminated skill frontmatter") from None
    metadata = {}
    for index in range(1, end):
        match = re.match(r"^(name|description):\s*(.*)$", lines[index])
        if not match:
            continue
        key, value = match.groups()
        if value in {">", "|", ">-", "|-"}:
            block = []
            for line in lines[index + 1:end]:
                if line and not line[0].isspace():
                    break
                block.append(line.strip())
            value = (" " if value.startswith(">") else "\n").join(block).strip()
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        metadata[key] = value
    if not metadata.get("name") or not metadata.get("description"):
        raise ValueError("Skill requires a name and description")
    return metadata


class SkillLibrary:
    def __init__(self, root: Path = DEFAULT_SKILLS_ROOT):
        self.root = root.resolve()
        # One library instance per task. Keep metadata, not duplicate instruction text.
        self._loaded: dict[str, dict] = {}

    def _path(self, skill: str, document: str = "SKILL.md") -> Path:
        if not skill or Path(skill).name != skill or skill in {".", ".."}:
            raise ValueError("Use a skill directory name from list_skills")
        relative = Path(document)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Use a document path relative to the selected skill")
        base = self.root / skill
        target = base / relative
        for component in [target, *target.parents]:
            if component == self.root:
                break
            if component.is_symlink():
                raise ValueError("Symbolic links are not allowed in skill paths")
        if not target.resolve().is_relative_to(base.resolve()):
            raise ValueError("Document escapes selected skill")
        if not target.is_file() or target.stat().st_nlink > 1:
            raise ValueError("Document must be a regular, non-hard-linked file")
        if target.suffix.lower() not in {".md", ".txt", ".rst"}:
            raise ValueError("Only text documentation (.md, .txt, .rst) is available")
        return target

    def _text(self, skill: str, document: str) -> str:
        return self._path(skill, document).read_text(encoding="utf-8")

    def list_skills(self) -> dict:
        """Discover skill directory names and descriptions without loading instructions."""
        skills, errors = [], []
        if not self.root.is_dir():
            return {"error": "Skills directory does not exist"}
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir():
                continue
            try:
                metadata = _metadata(self._text(directory.name, "SKILL.md"))
                skills.append({"name": directory.name, "title": metadata["name"],
                               "description": metadata["description"]})
            except (OSError, ValueError) as exc:
                errors.append({"name": directory.name, "error": str(exc)})
        return {"skills": skills, "errors": errors}

    def load_skill(self, skill: str) -> dict:
        """Load a selected skill's instructions and list its documentation paths.

        If instructions are truncated, continue SKILL.md using read_skill_document.
        Load each skill once per task; repeat calls return a short reminder.
        Loading a skill does not execute code or grant additional tools.
        """
        if skill in self._loaded:
            return {**self._loaded[skill], "already_loaded": True,
                    "message": "Instructions were already loaded in this task. Reuse them; "
                               "search/read the listed references with read_skill_document. "
                               "If next_line is set, continue SKILL.md at that line."}
        try:
            text = self._text(skill, "SKILL.md")
            _metadata(text)
            documents = []
            # Path.rglob does not descend symlink directories on Python 3.12.
            for candidate in sorted((self.root / skill).rglob("*")):
                relative = candidate.relative_to(self.root / skill).as_posix()
                try:
                    self._path(skill, relative)
                except (OSError, ValueError):
                    continue
                documents.append(relative)
            lines = text.splitlines()
            content, next_line = self._page(lines, 1, len(lines), MAX_INSTRUCTION_CHARS)
            metadata = {"skill": skill, "document": "SKILL.md", "total_lines": len(lines),
                        "next_line": next_line, "documents": documents}
            self._loaded[skill] = metadata
            return {**metadata, "content": content}
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}

    @staticmethod
    def _page(lines: list[str], start: int, count: int, char_limit: int) -> tuple[str, int | None]:
        selected, size = [], 0
        for index in range(start - 1, min(start - 1 + count, len(lines))):
            line = lines[index]
            # Never silently truncate a long line or skip its remainder.
            if len(line) + 1 > char_limit and not selected:
                raise ValueError("Single line exceeds retrieval limit")
            if size + len(line) + 1 > char_limit:
                break
            selected.append(line)
            size += len(line) + 1
        following = start + len(selected)
        return "\n".join(selected), following if following <= len(lines) else None

    def read_skill_document(self, skill: str, document: str = "SKILL.md",
                            start_line: int = 1, line_count: int = 80, query: str = "") -> dict:
        """Read a bounded line range, or search a skill document for a literal query.

        Lines are 1-based; line_count is capped at 120 and content at 6000 characters.
        A nonempty query returns up to 20 matching line numbers/snippets instead
        of a page. Search for headings/topics, then read relevant line ranges.
        Continue a page using next_line; null means end of document.
        """
        try:
            if start_line < 1 or line_count < 1:
                raise ValueError("start_line and line_count must be positive")
            _metadata(self._text(skill, "SKILL.md"))
            lines = self._text(skill, document).splitlines()
            if start_line > max(1, len(lines)):
                raise ValueError("start_line exceeds document length")
            result = {"skill": skill, "document": document, "total_lines": len(lines)}
            if query:
                matches = [{"line": i + 1, "text": line[:240]}
                           for i, line in enumerate(lines) if query.casefold() in line.casefold()
                           and i + 1 >= start_line]
                return {**result, "matches": matches[:20], "more_matches": len(matches) > 20}
            content, next_line = self._page(lines, start_line, min(line_count, MAX_LINES),
                                            MAX_DOCUMENT_CHARS)
            return {**result, "start_line": start_line, "content": content,
                    "next_line": next_line}
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}
