from pathlib import Path

import pytest

from app.services.bibliography_contract import (
    BibliographyContractError,
    discover_bibliography_sources,
    load_bibmeta_manifest,
    resolve_bibliography_source,
)
from app.services.parser import clean_latex_string, normalize_venue, parse_bib_file


def test_clean_latex_string():
    """Test LaTeX to Unicode conversion."""
    assert clean_latex_string(r"Sch\"{o}nberg") == "Schönberg"
    assert clean_latex_string(r"Caf\'{e}") == "Café"
    assert clean_latex_string("{Deep} {Learning}") == "Deep Learning"
    assert clean_latex_string("") == ""
    assert clean_latex_string("Hello World") == "Hello World"


def test_clean_latex_string_ifmmode_conditionals():
    r"""Test \ifmmode conditional patterns used by APS journal exports."""
    # Single caron via \ifmmode
    assert clean_latex_string(r"\ifmmode \check{c}\else \v{c}\fi{}") == "č"
    assert clean_latex_string(r"\ifmmode\check{c}\else\v{c}\fi{}") == "č"
    # Acute accent via \ifmmode
    assert clean_latex_string(r"\ifmmode \acute{c}\else \'{c}\fi{}") == "ć"
    # Dot-above via \ifmmode
    assert clean_latex_string(r"\ifmmode \dot{Z}\else \.{Z}\fi{}") == "Ż"
    # Cedilla via \ifmmode (\mbox variant)
    assert clean_latex_string(r"\ifmmode \mbox{\c{c}}\else \c{c}\fi{}ois") == "çois"


def test_clean_latex_string_accented_names():
    """Test common accented name patterns."""
    assert clean_latex_string(r"T\"ucker") == "Tücker"
    assert clean_latex_string(r"Mu\~noz") == "Muñoz"
    assert clean_latex_string(r"\v{S}") == "Š"
    assert clean_latex_string(r"R\'evai") == "Révai"
    assert clean_latex_string(r"L\'{o}pez") == "López"
    assert clean_latex_string(r"\v{S}\'arka") == "Šárka"


def test_discover_bibliography_sources_uses_bibmeta_contract(tmp_path: Path):
    (tmp_path / "meta").mkdir()
    (tmp_path / "books").mkdir()
    (tmp_path / "collections").mkdir()
    (tmp_path / "collections" / "_archive").mkdir()

    (tmp_path / "meta" / "bibmeta.toml").write_text(
        """
version = 1

[[rules]]
glob = "books/*.bib"
role = "canonical"
subject = "{stem}"

[[rules]]
glob = "collections/*.bib"
exclude = ["collections/_archive/**/*.bib"]
role = "curated"
topics = ["{stem}"]

[[rules]]
glob = "collections/_archive/**/*.bib"
role = "archive"
        """.strip(),
        encoding="utf-8",
    )
    (tmp_path / "books" / "cs-ml-ai.bib").write_text(
        "@article{bookpaper, title={Book Paper}}",
        encoding="utf-8",
    )
    (tmp_path / "collections" / "transformers.bib").write_text(
        "@article{transformerpaper, title={Transformer Paper}}",
        encoding="utf-8",
    )
    (tmp_path / "collections" / "_archive" / "legacy.bib").write_text(
        "@article{legacy, title={Legacy Paper}}",
        encoding="utf-8",
    )

    sources = discover_bibliography_sources(tmp_path)

    assert [source.source_file for source in sources] == [
        "books/cs-ml-ai.bib",
        "collections/transformers.bib",
    ]
    assert sources[0].role == "canonical"
    assert sources[0].subject == "cs-ml-ai"
    assert sources[1].role == "curated"
    assert sources[1].topics == ("transformers",)


def test_parse_bib_file_applies_source_context(tmp_path: Path):
    (tmp_path / "meta").mkdir()
    (tmp_path / "books").mkdir()
    (tmp_path / "meta" / "bibmeta.toml").write_text(
        """
version = 1

[[rules]]
glob = "books/*.bib"
role = "canonical"
subject = "{stem}"
        """.strip(),
        encoding="utf-8",
    )
    bib_file = tmp_path / "books" / "cs-ml-ai.bib"
    bib_file.write_text(
        """
@article{smith2024,
  title = {Deep Learning Notes},
  author = {Smith, Alice and Jones, Bob},
  year = {2024},
}
        """.strip(),
        encoding="utf-8",
    )

    manifest = load_bibmeta_manifest(tmp_path / "meta" / "bibmeta.toml")
    source = resolve_bibliography_source(
        bib_file,
        repo_root=tmp_path,
        manifest=manifest,
    )
    entries = parse_bib_file(bib_file, source=source)

    assert len(entries) == 1
    assert entries[0]["source_file"] == "books/cs-ml-ai.bib"
    assert entries[0]["source_role"] == "canonical"
    assert entries[0]["subject"] == "cs-ml-ai"
    assert entries[0]["topics"] == []


def test_resolve_bibliography_source_rejects_legacy_namespaces(tmp_path: Path):
    (tmp_path / "meta").mkdir()
    (tmp_path / "books").mkdir()
    (tmp_path / "meta" / "bibmeta.toml").write_text(
        """
version = 1

[[rules]]
glob = "books/*.bib"
role = "canonical"
subject = "{stem}"
        """.strip(),
        encoding="utf-8",
    )
    bib_file = tmp_path / "books" / "cs-ml-ai.bib"
    bib_file.write_text(
        """
@COMMENT{mundaneum:
subject = cs-ml-ai
}
@article{smith2024, title={Legacy}}
        """.strip(),
        encoding="utf-8",
    )

    manifest = load_bibmeta_manifest(tmp_path / "meta" / "bibmeta.toml")
    with pytest.raises(BibliographyContractError):
        resolve_bibliography_source(
            bib_file,
            repo_root=tmp_path,
            manifest=manifest,
        )


def test_normalize_venue():
    assert (
        normalize_venue("Advances in Neural Information Processing Systems")
        == "neurips"
    )
    assert normalize_venue("NeurIPS") == "neurips"
    assert (
        normalize_venue("International Conference on Learning Representations")
        == "iclr"
    )
    assert normalize_venue("Nature") == "nature"
    assert normalize_venue("Some Random Journal") is None
    assert normalize_venue("  Messy   Spacing  ") is None
