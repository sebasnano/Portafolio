#!/usr/bin/env python3
"""Validate the dependency-free public site from the repository root."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import ParseResult, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://ingseb.cloud"
ORIGIN_PARTS = urlparse(ORIGIN)
DEFAULT_PORTS = {"http": 80, "https": 443}
HTML_GLOBS = ("*.html", "casos/*.html")
PUBLIC_TEXT_GLOBS = (*HTML_GLOBS, "assets/*.css", "assets/*.svg", "robots.txt", "sitemap.xml")
MARKER_RE = re.compile(r"\b(?:TODO|FIXME|PLACEHOLDER)\b", re.IGNORECASE)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang: str | None = None
        self.title_parts: list[str] = []
        self.in_title = False
        self.counts = {"main": 0, "h1": 0}
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.refs: list[tuple[str, str, int]] = []
        self.meta: dict[tuple[str, str], str] = {}
        self.links: list[dict[str, str]] = []
        self.skip_links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = values.get("lang")
        if tag == "title":
            self.in_title = True
        if tag in self.counts:
            self.counts[tag] += 1
        element_id = values.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)
        for attribute in ("href", "src"):
            if values.get(attribute):
                self.refs.append((values[attribute], f"<{tag}> {attribute}", self.getpos()[0]))
        if tag == "meta":
            for key in ("name", "property"):
                if values.get(key):
                    self.meta[(key, values[key].lower())] = values.get("content", "").strip()
        if tag == "link":
            self.links.append(values)
        if tag == "a" and "skip-link" in values.get("class", "").split():
            self.skip_links.append(values)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()


def public_html_files() -> list[Path]:
    return sorted({path for pattern in HTML_GLOBS for path in ROOT.glob(pattern) if path.is_file()})


def public_text_files() -> list[Path]:
    return sorted({path for pattern in PUBLIC_TEXT_GLOBS for path in ROOT.glob(pattern) if path.is_file()})


def display(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def canonical_for(path: Path) -> str:
    relative = display(path)
    return f"{ORIGIN}/" if relative == "index.html" else f"{ORIGIN}/{relative}"


def same_origin(parsed: ParseResult) -> bool:
    scheme = (parsed.scheme or ORIGIN_PARTS.scheme).lower()
    if scheme != ORIGIN_PARTS.scheme or (parsed.hostname or "").lower() != ORIGIN_PARTS.hostname:
        return False
    try:
        port = parsed.port or DEFAULT_PORTS.get(scheme)
        origin_port = ORIGIN_PARTS.port or DEFAULT_PORTS.get(ORIGIN_PARTS.scheme)
    except ValueError:
        return False
    return port == origin_port


def local_target(source: Path, reference: str) -> tuple[Path, str] | None:
    parsed = urlparse(reference)
    scheme = parsed.scheme.lower()
    if scheme in {"mailto", "tel", "data", "javascript"}:
        return None
    if parsed.scheme or parsed.netloc:
        if not parsed.netloc or not same_origin(parsed):
            return None
        raw_path = parsed.path
    else:
        raw_path = parsed.path
    if not raw_path:
        target = source
    elif raw_path.startswith("/"):
        target = ROOT / unquote(raw_path.lstrip("/"))
    else:
        target = source.parent / unquote(raw_path)
    if raw_path.endswith("/") or target == ROOT:
        target = target / "index.html"
    try:
        target = target.resolve()
        target.relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return Path("/__outside_site__"), unquote(parsed.fragment)
    return target, unquote(parsed.fragment)


def require_meta(page: Path, parsed: PageParser, key: tuple[str, str], failures: list[str]) -> None:
    if not parsed.meta.get(key):
        failures.append(f"{display(page)}: missing or empty meta {key[0]}={key[1]!r}")


def validate_page(page: Path, parsed_pages: dict[Path, PageParser], failures: list[str]) -> None:
    parsed = parsed_pages[page]
    if not (parsed.html_lang or "").strip():
        failures.append(f"{display(page)}: <html> must declare a non-empty lang")
    if not parsed.title:
        failures.append(f"{display(page)}: <title> must not be empty")
    require_meta(page, parsed, ("name", "description"), failures)
    for name in ("og:type", "og:title", "og:description", "og:url", "og:image"):
        require_meta(page, parsed, ("property", name), failures)
    for name in ("twitter:card", "twitter:title", "twitter:description", "twitter:image"):
        require_meta(page, parsed, ("name", name), failures)
    canonical_links = [link for link in parsed.links if "canonical" in link.get("rel", "").lower().split()]
    expected = canonical_for(page)
    if len(canonical_links) != 1 or canonical_links[0].get("href") != expected:
        failures.append(f"{display(page)}: canonical must be exactly {expected!r}")
    if parsed.meta.get(("property", "og:url")) != expected:
        failures.append(f"{display(page)}: og:url must match canonical {expected!r}")
    favicons = [link for link in parsed.links if "icon" in link.get("rel", "").lower().split()]
    if len(favicons) != 1 or not favicons[0].get("href"):
        failures.append(f"{display(page)}: expected exactly one non-empty favicon link")
    for tag in ("main", "h1"):
        if parsed.counts[tag] != 1:
            failures.append(f"{display(page)}: expected exactly one <{tag}>, found {parsed.counts[tag]}")
    if parsed.duplicate_ids:
        failures.append(f"{display(page)}: duplicate ids: {', '.join(sorted(parsed.duplicate_ids))}")
    if len(parsed.skip_links) != 1:
        failures.append(f"{display(page)}: expected exactly one .skip-link, found {len(parsed.skip_links)}")
    else:
        target = local_target(page, parsed.skip_links[0].get("href", ""))
        if not target or target[0] != page.resolve() or not target[1] or target[1] not in parsed.ids:
            failures.append(f"{display(page)}: skip link must target an id on the same page")
    for reference, context, line in parsed.refs:
        target = local_target(page, reference)
        if target is None:
            continue
        target_path, fragment = target
        location = f"{display(page)}:{line}"
        if not target_path.is_file():
            failures.append(f"{location}: broken local reference {reference!r} ({context})")
        elif fragment:
            target_page = parsed_pages.get(target_path)
            if target_page is None:
                failures.append(f"{location}: fragment points to non-HTML target {reference!r}")
            elif fragment not in target_page.ids:
                failures.append(f"{location}: missing fragment #{fragment} in {display(target_path)}")


def validate_sitemap(pages: list[Path], failures: list[str]) -> None:
    sitemap = ROOT / "sitemap.xml"
    try:
        root = ET.parse(sitemap).getroot()
    except (ET.ParseError, OSError) as error:
        failures.append(f"sitemap.xml: not parseable XML: {error}")
        return
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    if root.tag != f"{namespace}urlset":
        failures.append("sitemap.xml: root must be the sitemap urlset element")
    locations = [(node.text or "").strip() for node in root.findall(f"{namespace}url/{namespace}loc")]
    expected = {canonical_for(page) for page in pages}
    actual = set(locations)
    for url in sorted(expected - actual):
        failures.append(f"sitemap.xml: missing public page {url}")
    for url in sorted(actual - expected):
        failures.append(f"sitemap.xml: URL does not map to a public HTML page: {url}")
    if len(locations) != len(actual):
        failures.append("sitemap.xml: duplicate <loc> entries found")


def robots_groups(content: str) -> list[tuple[set[str], list[tuple[str, str]]]]:
    groups: list[tuple[set[str], list[tuple[str, str]]]] = []
    agents: set[str] = set()
    rules: list[tuple[str, str]] = []
    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = set(), []
            agents.add(value.lower())
        elif agents:
            rules.append((field, value))
    if agents:
        groups.append((agents, rules))
    return groups


def validate_robots(failures: list[str]) -> None:
    robots = ROOT / "robots.txt"
    try:
        content = robots.read_text(encoding="utf-8")
    except OSError as error:
        failures.append(f"robots.txt: cannot read file: {error}")
        return
    if not re.search(rf"(?im)^\s*Sitemap:\s*{re.escape(ORIGIN)}/sitemap\.xml\s*$", content):
        failures.append(f"robots.txt: must reference {ORIGIN}/sitemap.xml")
    for agents, rules in robots_groups(content):
        if "*" in agents and any(field == "disallow" and value == "/" for field, value in rules):
            failures.append("robots.txt: User-agent: * must not use Disallow: /")
            break


def main() -> int:
    failures: list[str] = []
    pages = public_html_files()
    parsed_pages: dict[Path, PageParser] = {}
    for page in pages:
        parser = PageParser()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
            parser.close()
        except (OSError, UnicodeError) as error:
            failures.append(f"{display(page)}: cannot parse HTML: {error}")
        parsed_pages[page.resolve()] = parser
    for page in pages:
        validate_page(page.resolve(), parsed_pages, failures)
    validate_sitemap(pages, failures)
    validate_robots(failures)
    for path in public_text_files():
        try:
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if MARKER_RE.search(line):
                    failures.append(f"{display(path)}:{line_number}: public placeholder marker found")
        except (OSError, UnicodeError) as error:
            failures.append(f"{display(path)}: cannot scan public content: {error}")
    if failures:
        print(f"FAIL: site validation found {len(failures)} issue(s):", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print(f"PASS: validated {len(pages)} HTML pages, sitemap, robots.txt, local references, metadata, and public-content markers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
