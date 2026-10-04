import pytest

from app.services.search_intelligence import (
    SearchIntelligenceError,
    analyze_html,
    validate_public_url,
)


GOOD_HTML = """
<!doctype html>
<html>
<head>
  <title>AI Search Optimization Guide for Creators</title>
  <meta name="description" content="A practical guide to improving content structure, clarity, and search discoverability.">
  <meta name="author" content="CreatorOS Team">
  <meta property="og:title" content="AI Search Optimization Guide">
  <link rel="canonical" href="https://example.com/guides/ai-search">
  <script type="application/ld+json">{"@type":"Article"}</script>
</head>
<body>
  <h1>AI Search Optimization Guide for Creators</h1>
  <p>What is AI search optimization? It is the process of making useful, crawlable content easier for people and search systems to understand.</p>
  <h2>Build clear answers</h2>
  <p>Use direct explanations, practical examples, original evidence, and descriptive headings. This sample paragraph is intentionally repeated to provide enough readable content for the analyzer.</p>
  <p>Use direct explanations, practical examples, original evidence, and descriptive headings. This sample paragraph is intentionally repeated to provide enough readable content for the analyzer.</p>
  <p>Use direct explanations, practical examples, original evidence, and descriptive headings. This sample paragraph is intentionally repeated to provide enough readable content for the analyzer.</p>
  <p>Use direct explanations, practical examples, original evidence, and descriptive headings. This sample paragraph is intentionally repeated to provide enough readable content for the analyzer.</p>
  <p>Use direct explanations, practical examples, original evidence, and descriptive headings. This sample paragraph is intentionally repeated to provide enough readable content for the analyzer.</p>
  <p>Use direct explanations, practical examples, original evidence, and descriptive headings. This sample paragraph is intentionally repeated to provide enough readable content for the analyzer.</p>
  <h2>Structure the page</h2>
  <ul><li>Use one H1</li><li>Add descriptive H2 sections</li><li>Link related resources</li></ul>
  <h2>Support important claims</h2>
  <p>Link to trustworthy sources and make authorship clear.</p>
  <a href="/related">Related guide</a>
  <a href="/examples">Examples</a>
  <a href="/checklist">Checklist</a>
  <a href="https://developers.google.com/search/">Google Search documentation</a>
  <a href="https://schema.org/">Schema.org</a>
  <img src="/diagram.png" alt="Search optimization workflow">
</body>
</html>
"""


WEAK_HTML = """
<html>
<head><title>Hi</title></head>
<body><p>Short page.</p><img src="/x.png"></body>
</html>
"""


def test_search_readiness_scores_stronger_page_higher():
    strong = analyze_html(GOOD_HTML, "https://example.com/guides/ai-search")
    weak = analyze_html(WEAK_HTML, "https://example.com/thin")

    assert strong["score"] > weak["score"]
    assert strong["scores"]["technical_seo"] >= 70
    assert strong["page"]["structured_data_blocks"] == 1
    assert strong["page"]["author_signal"] is True
    assert strong["page"]["internal_links"] == 3
    assert strong["source"] == "creatoros-rules-v1"
    assert "not a Google or AI-platform ranking score" in strong["methodology"]


def test_search_readiness_returns_actionable_issues():
    result = analyze_html(WEAK_HTML, "https://example.com/thin")

    categories = {issue["category"] for issue in result["issues"]}
    assert "discoverability" in categories
    assert "answer_clarity" in categories
    assert result["recommendations"]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/docs",
        "http://10.0.0.1/",
        "ftp://example.com/file",
    ],
)
def test_search_intelligence_blocks_private_or_unsupported_targets(url):
    with pytest.raises(SearchIntelligenceError):
        validate_public_url(url)
