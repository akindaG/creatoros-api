from __future__ import annotations

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx


MAX_HTML_BYTES = 1_500_000
MAX_REDIRECTS = 3
FETCH_TIMEOUT_SECONDS = 8.0
USER_AGENT = "CreatorOS-Search-Intelligence/1.0"


class SearchIntelligenceError(RuntimeError):
    pass


class _PageParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.base_host = (urlparse(base_url).hostname or "").lower()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.current_heading: str | None = None
        self.heading_buffer: list[str] = []
        self.h1: list[str] = []
        self.h2_count = 0
        self.h3_count = 0
        self.list_items = 0
        self.meta_description: str | None = None
        self.robots: str | None = None
        self.canonical_url: str | None = None
        self.images = 0
        self.images_with_alt = 0
        self.internal_links = 0
        self.external_links = 0
        self.structured_data_blocks = 0
        self.author_signal = False
        self.open_graph_signal = False
        self._inside_title = False
        self._skip_depth = 0

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key.lower(): (value or "").strip() for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        data = self._attrs(attrs)

        if tag in {"script", "style", "noscript", "svg"}:
            if tag == "script" and data.get("type", "").lower() == "application/ld+json":
                self.structured_data_blocks += 1
            self._skip_depth += 1
            return

        if self._skip_depth:
            return

        if tag == "title":
            self._inside_title = True
        elif tag in {"h1", "h2", "h3"}:
            self.current_heading = tag
            self.heading_buffer = []
        elif tag == "li":
            self.list_items += 1
        elif tag == "meta":
            name = data.get("name", "").lower()
            prop = data.get("property", "").lower()
            content = data.get("content", "").strip()
            if name == "description" and content:
                self.meta_description = content
            if name == "robots" and content:
                self.robots = content
            if name == "author" and content:
                self.author_signal = True
            if prop in {"og:title", "og:description", "og:url", "og:type"} and content:
                self.open_graph_signal = True
        elif tag == "link":
            rel = data.get("rel", "").lower()
            href = data.get("href", "").strip()
            if "canonical" in rel and href:
                self.canonical_url = urljoin(self.base_url, href)
        elif tag == "img":
            self.images += 1
            if data.get("alt", "").strip():
                self.images_with_alt += 1
        elif tag == "a":
            href = data.get("href", "").strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                return
            resolved = urljoin(self.base_url, href)
            parsed = urlparse(resolved)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return
            if parsed.hostname.lower() == self.base_host:
                self.internal_links += 1
            else:
                self.external_links += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return

        if self._skip_depth:
            return

        if tag == "title":
            self._inside_title = False
        elif tag == self.current_heading:
            heading = " ".join(self.heading_buffer).strip()
            if heading:
                if tag == "h1":
                    self.h1.append(heading)
                elif tag == "h2":
                    self.h2_count += 1
                elif tag == "h3":
                    self.h3_count += 1
            self.current_heading = None
            self.heading_buffer = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        if self._inside_title:
            self.title_parts.append(clean)
        if self.current_heading:
            self.heading_buffer.append(clean)
        self.text_parts.append(clean)


def _is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SearchIntelligenceError("Only http and https URLs can be analyzed.")
    if not parsed.hostname:
        raise SearchIntelligenceError("The URL must include a valid hostname.")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        raise SearchIntelligenceError("Local or private network addresses cannot be analyzed.")

    try:
        literal = ipaddress.ip_address(hostname)
        if not _is_public_ip(str(literal)):
            raise SearchIntelligenceError("Local or private network addresses cannot be analyzed.")
        return
    except ValueError:
        pass

    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SearchIntelligenceError("The website hostname could not be resolved.") from exc

    resolved = {item[4][0] for item in addresses}
    if not resolved or any(not _is_public_ip(address) for address in resolved):
        raise SearchIntelligenceError("Local or private network addresses cannot be analyzed.")


def _fetch_html(url: str) -> tuple[str, str, int]:
    current = url
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

    with httpx.Client(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False, headers=headers) as client:
        for _ in range(MAX_REDIRECTS + 1):
            validate_public_url(current)
            try:
                with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise SearchIntelligenceError("The website returned an invalid redirect.")
                        current = urljoin(current, location)
                        continue

                    if response.status_code >= 400:
                        raise SearchIntelligenceError(f"The website returned HTTP {response.status_code}.")

                    content_type = response.headers.get("content-type", "").lower()
                    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                        raise SearchIntelligenceError("The URL did not return an HTML page.")

                    declared = response.headers.get("content-length")
                    if declared:
                        try:
                            if int(declared) > MAX_HTML_BYTES:
                                raise SearchIntelligenceError("The page is too large to analyze safely.")
                        except ValueError:
                            pass

                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_HTML_BYTES:
                            raise SearchIntelligenceError("The page is too large to analyze safely.")

                    encoding = response.encoding or "utf-8"
                    return body.decode(encoding, errors="replace"), str(response.url), response.status_code
            except httpx.TimeoutException as exc:
                raise SearchIntelligenceError("The website took too long to respond.") from exc
            except httpx.HTTPError as exc:
                raise SearchIntelligenceError("CreatorOS could not reach the website.") from exc

    raise SearchIntelligenceError("The website redirected too many times.")


def _clamp(value: int) -> int:
    return max(0, min(100, int(round(value))))


def _score_page(parser: _PageParser, final_url: str) -> tuple[dict, list[dict], list[str]]:
    title = " ".join(parser.title_parts).strip() or None
    robots = (parser.robots or "").lower()
    word_count = len(" ".join(parser.text_parts).split())
    indexable = "noindex" not in robots
    alt_ratio = (parser.images_with_alt / parser.images) if parser.images else 1.0

    technical = 0
    technical += 18 if title else 0
    technical += 12 if parser.meta_description else 0
    technical += 10 if parser.canonical_url else 0
    technical += 18 if len(parser.h1) == 1 else (9 if parser.h1 else 0)
    technical += 17 if indexable else 0
    technical += 10 if alt_ratio >= 0.8 else (5 if alt_ratio >= 0.5 else 0)
    technical += 10 if parser.structured_data_blocks else 0
    technical += 5 if urlparse(final_url).scheme == "https" else 0

    content_quality = 0
    content_quality += 35 if word_count >= 900 else (28 if word_count >= 600 else (18 if word_count >= 300 else (8 if word_count >= 120 else 0)))
    content_quality += 20 if parser.h2_count >= 3 else (12 if parser.h2_count >= 1 else 0)
    content_quality += 15 if parser.list_items >= 3 else (8 if parser.list_items else 0)
    content_quality += 15 if parser.internal_links >= 3 else (8 if parser.internal_links else 0)
    content_quality += 15 if parser.external_links >= 1 else 0

    first_text = " ".join(parser.text_parts[:40]).strip()
    question_headings = sum(1 for h in parser.h1 if "?" in h)
    answer_clarity = 0
    answer_clarity += 30 if parser.h1 else 0
    answer_clarity += 25 if 80 <= len(first_text) <= 900 else (15 if first_text else 0)
    answer_clarity += 20 if parser.h2_count >= 2 else (10 if parser.h2_count else 0)
    answer_clarity += 15 if parser.list_items else 0
    answer_clarity += 10 if question_headings or any(token in first_text.lower() for token in ("what is", "how to", "why ", "best ", "guide")) else 0

    structured_content = 0
    structured_content += 30 if parser.h2_count >= 3 else (18 if parser.h2_count else 0)
    structured_content += 20 if parser.h3_count >= 2 else (10 if parser.h3_count else 0)
    structured_content += 20 if parser.list_items >= 3 else (10 if parser.list_items else 0)
    structured_content += 20 if parser.structured_data_blocks else 0
    structured_content += 10 if parser.canonical_url else 0

    authority = 0
    authority += 30 if parser.author_signal else 0
    authority += 25 if parser.external_links >= 2 else (15 if parser.external_links else 0)
    authority += 20 if parser.structured_data_blocks else 0
    authority += 15 if word_count >= 700 else (8 if word_count >= 300 else 0)
    authority += 10 if urlparse(final_url).scheme == "https" else 0

    discoverability = 0
    discoverability += 25 if indexable else 0
    discoverability += 20 if title else 0
    discoverability += 15 if parser.meta_description else 0
    discoverability += 15 if parser.canonical_url else 0
    discoverability += 15 if parser.open_graph_signal else 0
    discoverability += 10 if parser.internal_links else 0

    scores = {
        "technical_seo": _clamp(technical),
        "content_quality": _clamp(content_quality),
        "answer_clarity": _clamp(answer_clarity),
        "structured_content": _clamp(structured_content),
        "authority_signals": _clamp(authority),
        "discoverability": _clamp(discoverability),
    }

    issues: list[dict] = []
    recommendations: list[str] = []

    def add(severity: str, category: str, message: str, recommendation: str | None = None) -> None:
        issues.append({"severity": severity, "category": category, "message": message})
        if recommendation and recommendation not in recommendations:
            recommendations.append(recommendation)

    if not title:
        add("critical", "technical_seo", "No HTML title was detected.", "Add a descriptive, topic-focused page title.")
    elif len(title) < 20 or len(title) > 70:
        add("warning", "technical_seo", "The page title is unusually short or long.", "Refine the page title so it clearly describes the topic.")

    if not parser.meta_description:
        add("warning", "discoverability", "No meta description was detected.", "Add a concise meta description that summarizes the page value.")
    if not parser.h1:
        add("critical", "answer_clarity", "No H1 heading was detected.", "Add one clear H1 that states the page's primary topic.")
    elif len(parser.h1) > 1:
        add("warning", "structured_content", "Multiple H1 headings were detected.", "Use one primary H1 and organize supporting sections with H2/H3 headings.")
    if not indexable:
        add("critical", "discoverability", "The robots directive contains noindex.", "Remove noindex if this page is intended to appear in search.")
    if not parser.canonical_url:
        add("warning", "technical_seo", "No canonical URL was detected.", "Add a canonical link element for the preferred page URL.")
    if word_count < 300:
        add("warning", "content_quality", "The page contains limited readable text.", "Add enough original, useful content to fully answer the user's likely question.")
    if parser.h2_count < 2:
        add("warning", "structured_content", "The page has limited section structure.", "Break the content into descriptive H2 sections that match user questions.")
    if parser.images and alt_ratio < 0.8:
        add("warning", "technical_seo", "Several images are missing descriptive alt text.", "Add accurate alt text to meaningful images.")
    if not parser.structured_data_blocks:
        add("info", "structured_content", "No JSON-LD structured data block was detected.", "Where appropriate, add structured data that matches the visible page content.")
    if not parser.author_signal:
        add("info", "authority_signals", "No simple author metadata signal was detected.", "Make authorship and expertise clear when the content benefits from it.")
    if not parser.open_graph_signal:
        add("info", "discoverability", "Open Graph metadata was not detected.", "Add Open Graph metadata for clearer social and link previews.")
    if parser.internal_links == 0:
        add("info", "discoverability", "No internal links were detected.", "Link to relevant pages on the same site to improve discovery and context.")
    if parser.external_links == 0:
        add("info", "authority_signals", "No external supporting links were detected.", "Cite trustworthy supporting sources where they genuinely improve the content.")

    if not recommendations:
        recommendations.append("The page has a solid technical foundation. Focus next on adding original evidence, examples, and direct answers that competitors do not provide.")

    return scores, issues, recommendations[:8]


def analyze_html(html: str, final_url: str, status_code: int = 200) -> dict:
    parser = _PageParser(final_url)
    parser.feed(html)
    parser.close()

    title = " ".join(parser.title_parts).strip() or None
    word_count = len(" ".join(parser.text_parts).split())
    scores, issues, recommendations = _score_page(parser, final_url)

    overall = _clamp(
        scores["technical_seo"] * 0.25
        + scores["content_quality"] * 0.25
        + scores["answer_clarity"] * 0.20
        + scores["structured_content"] * 0.10
        + scores["authority_signals"] * 0.10
        + scores["discoverability"] * 0.10
    )

    return {
        "url": final_url,
        "score": overall,
        "scores": scores,
        "page": {
            "status_code": status_code,
            "final_url": final_url,
            "title": title,
            "meta_description": parser.meta_description,
            "canonical_url": parser.canonical_url,
            "robots": parser.robots,
            "h1": parser.h1,
            "h2_count": parser.h2_count,
            "h3_count": parser.h3_count,
            "word_count": word_count,
            "internal_links": parser.internal_links,
            "external_links": parser.external_links,
            "images": parser.images,
            "images_with_alt": parser.images_with_alt,
            "structured_data_blocks": parser.structured_data_blocks,
            "author_signal": parser.author_signal,
            "open_graph_signal": parser.open_graph_signal,
        },
        "issues": issues,
        "recommendations": recommendations,
        "methodology": "CreatorOS heuristic readiness score: technical SEO 25%, content quality 25%, answer clarity 20%, structured content 10%, authority signals 10%, discoverability 10%. It is not a Google or AI-platform ranking score.",
        "source": "creatoros-rules-v1",
    }


def analyze_url(url: str) -> dict:
    html, final_url, status_code = _fetch_html(url)
    result = analyze_html(html, final_url, status_code)
    result["url"] = url
    return result
