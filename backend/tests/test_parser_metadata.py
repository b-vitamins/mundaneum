from app.services.parser import (
    clean_latex_string,
    normalize_venue,
    parse_folio_comment,
)


def test_clean_latex_string():
    """Test LaTeX to Unicode conversion."""
    # LaTeX accent commands
    assert clean_latex_string(r"Sch\"{o}nberg") == "Schönberg"
    assert clean_latex_string(r"Caf\'{e}") == "Café"

    # Curly brace wrappers (common in BibTeX titles)
    assert clean_latex_string("{Deep} {Learning}") == "Deep Learning"

    # Empty and None handling
    assert clean_latex_string("") == ""

    # Plain text should pass through unchanged
    assert clean_latex_string("Hello World") == "Hello World"


def test_parse_folio_comment_valid():
    content = """
    % Some random comment
    @COMMENT{folio:
        subject = cs-ml-ai,
        topics = transformers | attention | nlp
    }
    @article{...}
    """
    metadata = parse_folio_comment(content)
    assert metadata["subject"] == "cs-ml-ai"
    assert set(metadata["topics"]) == {"transformers", "attention", "nlp"}


def test_parse_folio_comment_empty():
    content = "@article{...}"
    metadata = parse_folio_comment(content)
    assert metadata == {}


def test_normalize_venue():
    # Test built-in mappings
    assert (
        normalize_venue("Advances in Neural Information Processing Systems")
        == "neurips"
    )
    assert normalize_venue("NeurIPS") == "neurips"
    assert (
        normalize_venue("International Conference on Learning Representations")
        == "iclr"
    )

    # Test clean pass-through (Expect None for unknown venues)
    assert normalize_venue("Nature") == "nature"
    assert normalize_venue("Some Random Journal") is None
    assert normalize_venue("  Messy   Spacing  ") is None
