from epub import safe_href


def test_safe_href_allows_https():
    assert safe_href("https://example.com/article") == "https://example.com/article"


def test_safe_href_rejects_javascript():
    assert safe_href("javascript:alert(1)") == ""


def test_safe_href_escapes_quotes():
    url = 'https://evil.example/x" onclick="alert(1)'
    safe = safe_href(url)
    assert safe == "https://evil.example/x&quot; onclick=&quot;alert(1)"
    assert '"' not in safe or "&quot;" in safe
