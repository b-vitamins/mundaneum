from app.services.parser import parse_folio_comment, normalize_venue


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
