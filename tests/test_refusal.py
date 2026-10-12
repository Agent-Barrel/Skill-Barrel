from step2step.refusal import looks_like_refusal, refusal_evidence


def test_opening_refusal_is_detected():
    text = "I can't help with bypassing that authentication check. It would…"
    assert looks_like_refusal(text)
    assert refusal_evidence(text) == ["i can't help with"]


def test_short_response_with_a_marker_anywhere():
    assert looks_like_refusal("Thanks for the context.\n\nI must decline this one.")


def test_long_working_response_that_merely_quotes_a_phrase_is_not_a_refusal():
    body = "Implemented the parser.\n" * 80 + "Note: the model said 'I can't help with' once in a comment."
    assert not looks_like_refusal(body)


def test_empty_and_plain_text():
    assert not looks_like_refusal(None)
    assert not looks_like_refusal("")
    assert not looks_like_refusal("Done. 189 tests pass.")
