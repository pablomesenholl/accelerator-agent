"""Small text-file tools confined to an operator-selected workspace."""
from pathlib import Path


class WorkspaceFiles:
    def __init__(self, workspace: Path, read_only_roots: tuple[Path, ...] = ()):
        self.root = workspace.expanduser().resolve()
        self.read_only_roots = tuple(path.resolve() for path in read_only_roots)
        if any(self.root.is_relative_to(root) for root in self.read_only_roots):
            raise ValueError("Workspace must be outside the read-only skills directory")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, path: str) -> Path:
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Use a relative path within the workspace")
        target = self.root / relative
        for component in [target, *target.parents]:
            if component == self.root:
                break
            if component.is_symlink():
                raise ValueError("Symbolic links are not allowed")
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("Path escapes workspace")
        if any(target.resolve().is_relative_to(root) for root in self.read_only_roots):
            raise ValueError("Skill files are read-only; use the skill documentation tools")
        if target.is_file() and target.stat().st_nlink > 1:
            raise ValueError("Hard-linked files are not allowed")
        return target

    def read_file(self, path: str) -> dict:
        """Read a UTF-8 text file at a workspace-relative path."""
        try:
            return {"content": self._path(path).read_text(encoding="utf-8")}
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}

    def write_file(self, path: str, content: str) -> dict:
        """Create or overwrite a UTF-8 file within the workspace."""
        try:
            target = self._path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return {"written": path}
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}

    def edit_file(self, path: str, old_text: str, new_text: str) -> dict:
        """Replace exactly one occurrence of old_text in a workspace file."""
        try:
            target = self._path(path)
            content = target.read_text(encoding="utf-8")
            if not old_text or content.count(old_text) != 1:
                raise ValueError("old_text must match exactly once")
            target.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
            return {"edited": path}
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}

    def list_files(self, path: str = ".") -> dict:
        """List immediate entries of a workspace directory."""
        try:
            return {"entries": sorted(p.name for p in self._path(path).iterdir())}
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}
