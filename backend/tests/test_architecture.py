import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

COMPOSITION_ROOT_IMPORTS = {
    ("app.app_context", "build_app_context"): {
        Path("app/main.py"),
        Path("app/cli/import_bibtex.py"),
        Path("app/cli/sync_meilisearch.py"),
    },
    ("app.runtime", "build_app_runtime"): {Path("app/app_context.py")},
    ("app.services.service_container", "build_service_container"): {
        Path("app/app_context.py"),
    },
}

MAX_LINES = {
    Path("app/runtime.py"): 140,
    Path("app/services/search_service.py"): 120,
    Path("app/services/s2_sync.py"): 220,
}


def _python_files() -> list[Path]:
    return sorted(
        path for path in APP_ROOT.rglob("*.py") if "__pycache__" not in path.parts
    )


def _module_imports(path: Path) -> list[tuple[str, str]]:
    tree = ast.parse(path.read_text(), filename=str(path))
    imports: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imports.append((node.module, alias.name))

    return imports


def test_composition_root_imports_stay_at_the_boundary():
    violations: list[str] = []

    for path in _python_files():
        relative_path = path.relative_to(APP_ROOT.parent)
        imports = set(_module_imports(path))

        for restricted_import, allowed_files in COMPOSITION_ROOT_IMPORTS.items():
            if restricted_import in imports and relative_path not in allowed_files:
                violations.append(
                    f"{relative_path} imports {restricted_import[1]} from {restricted_import[0]}"
                )

    assert violations == []


def test_runtime_orchestrators_stay_small():
    oversized = []

    for relative_path, max_lines in MAX_LINES.items():
        line_count = len((APP_ROOT.parent / relative_path).read_text().splitlines())
        if line_count > max_lines:
            oversized.append(
                f"{relative_path} has {line_count} lines (limit {max_lines})"
            )

    assert oversized == []
