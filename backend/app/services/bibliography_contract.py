"""
Repository-aware bibliography metadata resolution.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

VALID_BIBLIOGRAPHY_ROLES = {
    "canonical",
    "curated",
    "derived",
    "archive",
    "auxiliary",
}
INGESTABLE_BIBLIOGRAPHY_ROLES = {"canonical", "curated"}
_INLINE_LABEL = "bibmeta"
_LEGACY_NAMESPACES = ("folio", "mundaneum")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class BibliographyContractError(RuntimeError):
    """Raised when the bibliography repo violates the bibmeta contract."""


@dataclass(frozen=True, slots=True)
class BibmetaRule:
    name: str
    glob: str
    exclude: tuple[str, ...]
    role: str
    subject: str | None
    topics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BibmetaManifest:
    version: int
    rules: tuple[BibmetaRule, ...]
    path: Path


@dataclass(frozen=True, slots=True)
class InlineBibmetaBlock:
    start: int
    end: int
    body: str


@dataclass(frozen=True, slots=True)
class BibliographySourceFile:
    path: Path
    source_file: str
    role: str
    subject: str | None = None
    topics: tuple[str, ...] = ()

    @property
    def is_ingestable(self) -> bool:
        return self.role in INGESTABLE_BIBLIOGRAPHY_ROLES


def iter_bib_files(directory: Path) -> list[Path]:
    """Return all .bib files beneath a directory in stable order."""
    if not directory.exists():
        logger.warning("Directory does not exist: %s", directory)
        return []

    out: list[Path] = []
    for path in directory.rglob("*.bib"):
        if not path.is_file():
            continue
        if any(part in {".git", "__pycache__"} for part in path.parts):
            continue
        out.append(path)
    return sorted(set(out))


def discover_bibliography_sources(directory: Path) -> list[BibliographySourceFile]:
    """
    Discover ingestable bibliography files for a directory.

    If a bibliography-owned `meta/bibmeta.toml` manifest exists, use it to
    classify files and skip non-ingestable layers. Otherwise treat the directory
    as a plain canonical BibTeX tree.
    """
    directory = directory.resolve()
    manifest_path = directory / "meta" / "bibmeta.toml"

    if not manifest_path.exists():
        return [
            BibliographySourceFile(
                path=path,
                source_file=path.relative_to(directory).as_posix(),
                role="canonical",
            )
            for path in iter_bib_files(directory)
        ]

    manifest = load_bibmeta_manifest(manifest_path)
    sources = [
        resolve_bibliography_source(path, repo_root=directory, manifest=manifest)
        for path in iter_bib_files(directory)
    ]
    ingestable_sources = [source for source in sources if source.is_ingestable]
    return sorted(
        ingestable_sources,
        key=lambda source: (_role_sort_key(source.role), source.source_file),
    )


def resolve_bibliography_source(
    path: Path,
    *,
    repo_root: Path,
    manifest: BibmetaManifest,
    text: str | None = None,
) -> BibliographySourceFile:
    """Resolve the bibmeta-derived role and tags for one repository file."""
    repo_root = repo_root.resolve()
    path = path.resolve()
    relative_path = path.relative_to(repo_root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace") if text is None else text

    for namespace in _LEGACY_NAMESPACES:
        pattern = re.compile(
            rf"@COMMENT\s*\{{\s*{re.escape(namespace)}\s*:", re.IGNORECASE
        )
        if pattern.search(text):
            raise BibliographyContractError(
                f"{relative_path} uses legacy @{namespace} metadata; only @COMMENT{{bibmeta: ...}} is supported"
            )

    rule = _match_rule(relative_path, manifest)
    if rule is None:
        raise BibliographyContractError(
            f"{relative_path} does not match any rule in {manifest.path}"
        )

    resolved = {
        "role": rule.role,
        "subject": _expand_template(rule.subject, path),
        "topics": tuple(_expand_template(topic, path) for topic in rule.topics),
    }
    inline_blocks = find_inline_bibmeta_blocks(text)

    if len(inline_blocks) > 1:
        raise BibliographyContractError(
            f"{relative_path} defines multiple @COMMENT{{bibmeta: ...}} blocks"
        )

    if inline_blocks:
        inline_block = inline_blocks[0]
        if not _is_leading_trivia(text[: inline_block.start]):
            raise BibliographyContractError(
                f"{relative_path} has inline bibmeta after real BibTeX content"
            )

        inline_payload = _parse_inline_payload(inline_block.body)
        merged = _merge_inline_metadata(resolved, inline_payload)
        if _metadata_equal(resolved, merged):
            raise BibliographyContractError(
                f"{relative_path} redundantly restates path-derived bibmeta"
            )
        resolved = merged

    _validate_resolved_metadata(
        role=str(resolved["role"]),
        subject=resolved["subject"],
        topics=tuple(resolved["topics"]),
        context=relative_path,
    )

    return BibliographySourceFile(
        path=path,
        source_file=relative_path,
        role=str(resolved["role"]),
        subject=resolved["subject"],
        topics=tuple(resolved["topics"]),
    )


def load_bibmeta_manifest(path: Path) -> BibmetaManifest:
    """Load and validate the bibliography repo manifest."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - defensive
        raise BibliographyContractError(f"Could not parse {path}: {exc}") from exc

    version = data.get("version")
    if version != 1:
        raise BibliographyContractError(
            f"Unsupported bibmeta manifest version in {path}: {version!r}"
        )

    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise BibliographyContractError(
            f"{path} must contain a non-empty [[rules]] array"
        )

    rules: list[BibmetaRule] = []
    for index, raw_rule in enumerate(raw_rules, start=1):
        if not isinstance(raw_rule, dict):
            raise BibliographyContractError(f"Rule #{index} in {path} is not a table")
        rules.append(_load_rule(raw_rule, index=index, manifest_path=path))

    return BibmetaManifest(version=1, rules=tuple(rules), path=path)


def find_inline_bibmeta_blocks(text: str) -> list[InlineBibmetaBlock]:
    """Find inline @COMMENT{bibmeta: ...} blocks in raw file text."""
    blocks: list[InlineBibmetaBlock] = []
    upper = text.upper()
    cursor = 0

    while True:
        idx = upper.find("@COMMENT", cursor)
        if idx == -1:
            return blocks

        brace_idx = idx + len("@COMMENT")
        while brace_idx < len(text) and text[brace_idx].isspace():
            brace_idx += 1

        if brace_idx >= len(text) or text[brace_idx] != "{":
            cursor = idx + len("@COMMENT")
            continue

        end = _find_matching_brace(text, brace_idx)
        if end is None:
            cursor = brace_idx + 1
            continue

        inner = text[brace_idx + 1 : end].lstrip()
        if inner.lower().startswith(f"{_INLINE_LABEL}:"):
            body = inner[len(_INLINE_LABEL) + 1 :]
            blocks.append(
                InlineBibmetaBlock(
                    start=idx,
                    end=end + 1,
                    body=body,
                )
            )
        cursor = end + 1


def _load_rule(
    raw_rule: dict[str, Any], *, index: int, manifest_path: Path
) -> BibmetaRule:
    allowed = {"name", "glob", "exclude", "role", "subject", "topics"}
    extras = sorted(set(raw_rule) - allowed)
    if extras:
        raise BibliographyContractError(
            f"Rule #{index} in {manifest_path} has unknown keys: {', '.join(extras)}"
        )

    glob = raw_rule.get("glob")
    role = raw_rule.get("role")
    if not isinstance(glob, str) or not glob.strip():
        raise BibliographyContractError(
            f"Rule #{index} in {manifest_path} must define a non-empty glob"
        )
    if not isinstance(role, str) or role not in VALID_BIBLIOGRAPHY_ROLES:
        raise BibliographyContractError(
            f"Rule #{index} in {manifest_path} has invalid role {role!r}"
        )

    exclude = raw_rule.get("exclude", [])
    if exclude is None:
        exclude = []
    if not isinstance(exclude, list) or any(
        not isinstance(item, str) for item in exclude
    ):
        raise BibliographyContractError(
            f"Rule #{index} in {manifest_path} must define exclude as a list of strings"
        )

    subject = raw_rule.get("subject")
    if subject is not None and not isinstance(subject, str):
        raise BibliographyContractError(
            f"Rule #{index} in {manifest_path} must define subject as a string"
        )

    topics = raw_rule.get("topics", [])
    if topics is None:
        topics = []
    if not isinstance(topics, list) or any(
        not isinstance(item, str) for item in topics
    ):
        raise BibliographyContractError(
            f"Rule #{index} in {manifest_path} must define topics as a list of strings"
        )

    _validate_resolved_metadata(
        role=role,
        subject=subject,
        topics=tuple(topics),
        context=f"{manifest_path} rule #{index}",
        allow_templates=True,
    )

    return BibmetaRule(
        name=str(raw_rule.get("name") or f"rule-{index}"),
        glob=glob,
        exclude=tuple(exclude),
        role=role,
        subject=subject,
        topics=tuple(topics),
    )


def _match_rule(relative_path: str, manifest: BibmetaManifest) -> BibmetaRule | None:
    for rule in manifest.rules:
        if not _pattern_matches(relative_path, rule.glob):
            continue
        if any(_pattern_matches(relative_path, pattern) for pattern in rule.exclude):
            continue
        return rule
    return None


def _expand_template(template: str | None, path: Path) -> str | None:
    if template is None:
        return None
    return (
        template.replace("{stem}", path.stem)
        .replace("{parent}", path.parent.name)
        .replace("{grandparent}", path.parent.parent.name)
    )


def _parse_inline_payload(body: str) -> dict[str, Any]:
    try:
        payload = tomllib.loads(body)
    except tomllib.TOMLDecodeError as exc:
        raise BibliographyContractError(
            f"Could not parse inline bibmeta: {exc}"
        ) from exc

    allowed = {"role", "subject", "topics", "topics_append", "replace_topics"}
    extras = sorted(set(payload) - allowed)
    if extras:
        raise BibliographyContractError(
            f"Inline bibmeta has unknown keys: {', '.join(extras)}"
        )
    return payload


def _merge_inline_metadata(
    defaults: dict[str, Any],
    inline_payload: dict[str, Any],
) -> dict[str, Any]:
    merged = {
        "role": defaults["role"],
        "subject": defaults.get("subject"),
        "topics": tuple(defaults.get("topics") or ()),
    }

    if "role" in inline_payload:
        role = inline_payload["role"]
        if not isinstance(role, str) or role not in VALID_BIBLIOGRAPHY_ROLES:
            raise BibliographyContractError(f"Inline bibmeta has invalid role {role!r}")
        merged["role"] = role

    if "subject" in inline_payload:
        subject = inline_payload["subject"]
        if subject is not None and not isinstance(subject, str):
            raise BibliographyContractError("Inline bibmeta subject must be a string")
        merged["subject"] = subject

    if "replace_topics" in inline_payload:
        replace_topics = inline_payload["replace_topics"]
        if not isinstance(replace_topics, bool):
            raise BibliographyContractError(
                "Inline bibmeta replace_topics must be true or false"
            )
    else:
        replace_topics = False

    if "topics" in inline_payload:
        topics = _coerce_topics(inline_payload["topics"], field_name="topics")
        merged["topics"] = topics
    elif replace_topics:
        merged["topics"] = ()

    if "topics_append" in inline_payload:
        topics_append = _coerce_topics(
            inline_payload["topics_append"],
            field_name="topics_append",
        )
        merged["topics"] = tuple(dict.fromkeys((*merged["topics"], *topics_append)))

    return merged


def _coerce_topics(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise BibliographyContractError(
            f"Inline bibmeta {field_name} must be a list of strings"
        )
    return tuple(value)


def _validate_resolved_metadata(
    *,
    role: str,
    subject: str | None,
    topics: tuple[str, ...],
    context: str,
    allow_templates: bool = False,
) -> None:
    if role not in VALID_BIBLIOGRAPHY_ROLES:
        raise BibliographyContractError(f"{context} has invalid role {role!r}")

    if role == "canonical":
        if topics:
            raise BibliographyContractError(
                f"{context} cannot define topics for canonical files"
            )
    elif role == "curated":
        if subject is not None:
            raise BibliographyContractError(
                f"{context} cannot define a subject for curated files"
            )
        if not topics:
            raise BibliographyContractError(
                f"{context} must define at least one topic for curated files"
            )
    else:
        if subject is not None or topics:
            raise BibliographyContractError(
                f"{context} cannot define subject or topics for {role} files"
            )

    if subject is not None and not (
        _SLUG_RE.fullmatch(subject) or allow_templates and "{" in subject
    ):
        raise BibliographyContractError(
            f"{context} has invalid subject slug {subject!r}"
        )

    for topic in topics:
        if not (_SLUG_RE.fullmatch(topic) or allow_templates and "{" in topic):
            raise BibliographyContractError(
                f"{context} has invalid topic slug {topic!r}"
            )


def _metadata_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("role") == right.get("role")
        and left.get("subject") == right.get("subject")
        and tuple(left.get("topics") or ()) == tuple(right.get("topics") or ())
    )


def _is_leading_trivia(prefix: str) -> bool:
    for line in prefix.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("%"):
            continue
        return False
    return True


def _find_matching_brace(text: str, open_brace_idx: int) -> int | None:
    depth = 0
    in_string = False
    escaped = False

    for index in range(open_brace_idx, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _role_sort_key(role: str) -> int:
    if role == "canonical":
        return 0
    if role == "curated":
        return 1
    return 2


def _pattern_matches(relative_path: str, pattern: str) -> bool:
    return _match_pattern_parts(relative_path.split("/"), pattern.split("/"))


def _match_pattern_parts(path_parts: list[str], pattern_parts: list[str]) -> bool:
    if not pattern_parts:
        return not path_parts

    token = pattern_parts[0]
    if token == "**":
        return _match_pattern_parts(path_parts, pattern_parts[1:]) or (
            bool(path_parts) and _match_pattern_parts(path_parts[1:], pattern_parts)
        )

    if not path_parts:
        return False

    if not fnmatchcase(path_parts[0], token):
        return False
    return _match_pattern_parts(path_parts[1:], pattern_parts[1:])
