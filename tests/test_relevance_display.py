from gemini import article_relevance, relevance_display


def test_relevance_display_scales_to_ten():
    art = {"relevance": 85}
    assert article_relevance(art) == 85
    assert relevance_display(art) == "8.5"


def test_relevance_display_rounds_to_one_decimal():
    art = {"relevance": 72}
    assert relevance_display(art) == "7.2"
