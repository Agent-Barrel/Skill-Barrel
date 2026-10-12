from step2step.prompts import parse_prompts


def test_plain_split():
    assert parse_prompts("alpha\n---\nbeta") == ["alpha", "beta"]


def test_frontmatter_skipped():
    assert parse_prompts("---\ntitle: x\ntags: y\n---\nreal prompt") == ["real prompt"]


def test_leading_sep_not_yaml_is_separator():
    # A leading '---' whose block is not key: lines is a separator, not frontmatter.
    assert parse_prompts("---\nnot yaml here\n---\nsecond") == ["not yaml here", "second"]


def test_backtick_fence_separator_preserved():
    out = parse_prompts("intro\n```\ncode\n---\nmore\n```\ntail")
    assert len(out) == 1 and "---" in out[0]


def test_tilde_fence_separator_preserved():
    out = parse_prompts("intro\n~~~\ncode\n---\nmore\n~~~\ntail")
    assert len(out) == 1 and "---" in out[0]


def test_bom_stripped():
    assert parse_prompts("﻿alpha\n---\nbeta") == ["alpha", "beta"]


def test_blank_chunks_dropped():
    assert parse_prompts("a\n---\n\n---\nb") == ["a", "b"]
