#!/usr/bin/env python3
"""Validate the dependency-free public site from the repository root."""

from __future__ import annotations

import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from datetime import date
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
DISPLAY_DATE_RE = re.compile(r"\b(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4})\b")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
CASE_DIRECTORY = "casos"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_DIMENSIONS = (1200, 630)
PNG_ALLOWED_CHUNKS = {b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND"}


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
        self.meta_occurrences: dict[tuple[str, str], list[str]] = {}
        self.links: list[dict[str, str]] = []
        self.skip_links: list[dict[str, str]] = []
        self.json_ld_parts: list[list[str]] = []
        self.in_json_ld = False
        self.hidden_depth = 0
        self.time_contexts: list[tuple[int, str]] = []
        self.next_time_context = 0
        self.visible_text_parts: list[str] = []
        self.visible_text_contexts: list[tuple[int, int | None, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = values.get("lang")
        if tag == "title":
            self.in_title = True
        if tag in {"script", "style"}:
            self.hidden_depth += 1
        if tag == "script" and values.get("type", "").lower() == "application/ld+json":
            self.in_json_ld = True
            self.json_ld_parts.append([])
        if tag == "time":
            self.next_time_context += 1
            self.time_contexts.append((self.next_time_context, values.get("datetime", "")))
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
                    meta_key = (key, values[key].lower())
                    content = values.get("content", "").strip()
                    self.meta[meta_key] = content
                    self.meta_occurrences.setdefault(meta_key, []).append(content)
        if tag == "link":
            self.links.append(values)
        if tag == "a" and "skip-link" in values.get("class", "").split():
            self.skip_links.append(values)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "time" and self.time_contexts:
            self.time_contexts.pop()
        if tag == "script" and self.in_json_ld:
            self.in_json_ld = False
        if tag in {"script", "style"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_json_ld:
            self.json_ld_parts[-1].append(data)
        if not self.hidden_depth:
            time_context, enclosing_datetime = self.time_contexts[-1] if self.time_contexts else (None, None)
            line = self.getpos()[0]
            self.visible_text_parts.append(data)
            for character in data:
                self.visible_text_contexts.append((line, time_context, enclosing_datetime))
                if character == "\n":
                    line += 1

    @property
    def visible_dates(self) -> list[tuple[str, str | None, int]]:
        visible_text = "".join(self.visible_text_parts)
        dates: list[tuple[str, str | None, int]] = []
        for match in DISPLAY_DATE_RE.finditer(visible_text):
            contexts = self.visible_text_contexts[match.start() : match.end()]
            time_ids = {context[1] for context in contexts}
            enclosing_datetime = contexts[0][2] if len(time_ids) == 1 and None not in time_ids else None
            dates.append((match.group(0), enclosing_datetime, contexts[0][0]))
        return dates

    @property
    def json_ld_blocks(self) -> list[str]:
        return ["".join(parts).strip() for parts in self.json_ld_parts]

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


def parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def article_objects(value: object) -> list[dict[str, object]]:
    articles: list[dict[str, object]] = []
    if isinstance(value, list):
        for item in value:
            articles.extend(article_objects(item))
    elif isinstance(value, dict):
        schema_type = value.get("@type")
        if schema_type == "Article" or (isinstance(schema_type, list) and "Article" in schema_type):
            articles.append(value)
        for nested_value in value.values():
            if isinstance(nested_value, (dict, list)):
                articles.extend(article_objects(nested_value))
    return articles


def article_metadata(page: Path, parsed: PageParser, failures: list[str]) -> dict[str, object] | None:
    articles: list[dict[str, object]] = []
    for block_number, block in enumerate(parsed.json_ld_blocks, 1):
        try:
            structured_data = json.loads(block)
        except json.JSONDecodeError as error:
            failures.append(f"{display(page)}: JSON-LD block {block_number} is not valid JSON: {error.msg}")
            continue
        articles.extend(article_objects(structured_data))
    if len(articles) != 1:
        failures.append(f"{display(page)}: expected exactly one parseable Article JSON-LD object, found {len(articles)}")
        return None
    return articles[0]


def validate_case_dates(page: Path, parsed: PageParser, failures: list[str]) -> str | None:
    article = article_metadata(page, parsed, failures)
    modified_text: str | None = None
    if article is not None:
        published_text = article.get("datePublished")
        modified_value = article.get("dateModified")
        published = parse_iso_date(published_text)
        modified = parse_iso_date(modified_value)
        if published is None:
            failures.append(f"{display(page)}: Article datePublished must be a valid YYYY-MM-DD date")
        if modified is None:
            failures.append(f"{display(page)}: Article dateModified must be a valid YYYY-MM-DD date")
        elif isinstance(modified_value, str):
            modified_text = modified_value
        if published is not None and modified is not None and modified < published:
            failures.append(f"{display(page)}: Article dateModified must not precede datePublished")
    for visible_date, enclosing_datetime, line in parsed.visible_dates:
        day, month, year = visible_date.split("/")
        expected = f"{year}-{month}-{day}"
        if parse_iso_date(expected) is None:
            failures.append(f"{display(page)}:{line}: visible date {visible_date!r} is not a valid calendar date")
        elif enclosing_datetime != expected:
            failures.append(
                f"{display(page)}:{line}: visible date {visible_date!r} must be inside "
                f"<time datetime={expected!r}>"
            )
    return modified_text


def require_meta(page: Path, parsed: PageParser, key: tuple[str, str], failures: list[str]) -> None:
    occurrences = parsed.meta_occurrences.get(key, [])
    if not occurrences:
        failures.append(f"{display(page)}: missing or empty meta {key[0]}={key[1]!r}")
    elif len(occurrences) != 1:
        failures.append(
            f"{display(page)}: meta {key[0]}={key[1]!r} must occur exactly once, found {len(occurrences)}"
        )
    elif not occurrences[0]:
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


def decode_case_png(path: Path) -> tuple[bytes | None, list[str]]:
    """Return reconstructed RGBA scanlines and structural PNG errors."""
    errors: list[str] = []
    try:
        payload = path.read_bytes()
    except OSError as error:
        return None, [f"cannot read PNG: {error}"]
    if not payload.startswith(PNG_SIGNATURE):
        return None, ["invalid PNG signature"]

    offset = len(PNG_SIGNATURE)
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(payload):
        if offset + 12 > len(payload):
            errors.append("truncated PNG chunk")
            break
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(payload):
            errors.append(f"truncated {chunk_type.decode('ascii', 'replace')} chunk")
            break
        data = payload[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + length : chunk_end])[0]
        actual_crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            errors.append(f"invalid {chunk_type.decode('ascii', 'replace')} chunk CRC")
        chunks.append((chunk_type, data))
        offset = chunk_end
        if chunk_type == b"IEND":
            if offset != len(payload):
                errors.append("data found after IEND")
            break

    chunk_types = [chunk_type for chunk_type, _ in chunks]
    for chunk_type in chunk_types:
        if chunk_type not in PNG_ALLOWED_CHUNKS:
            errors.append(
                f"PNG chunk {chunk_type.decode('ascii', 'replace')} is not allowed; "
                "expected only IHDR, optional PLTE/tRNS, IDAT, and IEND"
            )
    if not chunks or chunk_types[0] != b"IHDR" or chunk_types.count(b"IHDR") != 1:
        errors.append("PNG must contain exactly one leading IHDR chunk")
        return None, errors
    if chunk_types.count(b"IEND") != 1 or chunk_types[-1] != b"IEND":
        errors.append("PNG must contain exactly one trailing IEND chunk")
    if b"IDAT" not in chunk_types:
        errors.append("PNG must contain IDAT data")

    ihdr = chunks[0][1]
    if len(ihdr) != 13:
        errors.append("IHDR must be 13 bytes")
        return None, errors
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", ihdr)
    if (width, height) != PNG_DIMENSIONS:
        errors.append(f"PNG dimensions must be 1200x630, found {width}x{height}")
    valid_depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
    if bit_depth not in valid_depths.get(color_type, set()):
        errors.append(f"invalid PNG bit depth/color type combination: {bit_depth}/{color_type}")
    if bit_depth != 8 or color_type != 6:
        errors.append(f"case card must be 8-bit RGBA PNG, found bit depth/color type {bit_depth}/{color_type}")
    if compression != 0 or filtering != 0:
        errors.append("unsupported PNG compression or filter method")
    if interlace != 0:
        errors.append("case card PNG must be non-interlaced")
    if errors:
        return None, errors

    compressed = b"".join(data for chunk_type, data in chunks if chunk_type == b"IDAT")
    try:
        filtered = zlib.decompress(compressed)
    except zlib.error as error:
        return None, [f"invalid compressed PNG data: {error}"]
    row_size = width * 4
    expected_size = height * (row_size + 1)
    if len(filtered) != expected_size:
        return None, [f"decoded PNG data has {len(filtered)} bytes; expected {expected_size}"]

    reconstructed = bytearray()
    prior = bytearray(row_size)
    for row_number in range(height):
        start = row_number * (row_size + 1)
        filter_type = filtered[start]
        current = bytearray(filtered[start + 1 : start + 1 + row_size])
        if filter_type > 4:
            return None, [f"invalid PNG filter type {filter_type} on row {row_number}"]
        for index, value in enumerate(current):
            left = current[index - 4] if index >= 4 else 0
            above = prior[index]
            upper_left = prior[index - 4] if index >= 4 else 0
            if filter_type == 1:
                current[index] = (value + left) & 0xFF
            elif filter_type == 2:
                current[index] = (value + above) & 0xFF
            elif filter_type == 3:
                current[index] = (value + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                predictor = left + above - upper_left
                distances = (abs(predictor - left), abs(predictor - above), abs(predictor - upper_left))
                current[index] = (value + (left, above, upper_left)[distances.index(min(distances))]) & 0xFF
        reconstructed.extend(current)
        prior = current
    return bytes(reconstructed), []


def validate_case_images(
    case_pages: list[Path], parsed_pages: dict[Path, PageParser], failures: list[str]
) -> None:
    seen_urls: dict[str, str] = {}
    seen_alts: dict[str, str] = {}
    seen_pixels: dict[bytes, str] = {}
    for page in case_pages:
        parsed = parsed_pages[page.resolve()]
        article = article_metadata(page.resolve(), parsed, failures)
        article_image = article.get("image") if article is not None else None
        if not isinstance(article_image, str) or not article_image.strip():
            failures.append(f"{display(page)}: Article image must be exactly one non-empty string")
            article_image = ""
        og_image = parsed.meta.get(("property", "og:image"), "")
        twitter_image = parsed.meta.get(("name", "twitter:image"), "")
        if not article_image or og_image != article_image or twitter_image != article_image:
            failures.append(f"{display(page)}: Article, og:image, and twitter:image must match")
        expected_url = f"{ORIGIN}/assets/social-{page.stem}.png"
        if article_image != expected_url or og_image != expected_url or twitter_image != expected_url:
            failures.append(f"{display(page)}: case image metadata must use {expected_url}")

        image_url = article_image if isinstance(article_image, str) and article_image else og_image
        parsed_url = urlparse(image_url)
        if not image_url or not parsed_url.scheme or not parsed_url.netloc or not same_origin(parsed_url):
            failures.append(f"{display(page)}: case image must use the canonical origin {ORIGIN}")
        if parsed_url.query or parsed_url.fragment or not parsed_url.path.endswith(".png"):
            failures.append(f"{display(page)}: case image URL must identify a .png without query or fragment")
        previous_url = seen_urls.setdefault(image_url, display(page)) if image_url else None
        if previous_url and previous_url != display(page):
            failures.append(f"{display(page)}: case image URL duplicates {previous_url}")

        require_meta(page.resolve(), parsed, ("property", "og:image:alt"), failures)
        require_meta(page.resolve(), parsed, ("name", "twitter:image:alt"), failures)
        og_alt = parsed.meta.get(("property", "og:image:alt"), "")
        twitter_alt = parsed.meta.get(("name", "twitter:image:alt"), "")
        if not og_alt or not twitter_alt:
            failures.append(f"{display(page)}: OG and Twitter image alts must be non-empty")
        if og_alt != twitter_alt:
            failures.append(f"{display(page)}: OG and Twitter image alts must match")
        previous_alt = seen_alts.setdefault(og_alt, display(page)) if og_alt else None
        if previous_alt and previous_alt != display(page):
            failures.append(f"{display(page)}: image alt duplicates {previous_alt}")

        expected_asset = ROOT / "assets" / f"social-{page.stem}.png"
        if not expected_asset.is_file():
            failures.append(f"{display(page)}: case image asset does not exist locally: {display(expected_asset)}")
        target = local_target(page.resolve(), image_url) if image_url else None
        if target is None or not target[0].is_file():
            continue
        pixels, png_errors = decode_case_png(target[0])
        for error in png_errors:
            failures.append(f"{display(page)}: {error}")
        if pixels is not None:
            previous_pixels = seen_pixels.setdefault(pixels, display(page))
            if previous_pixels != display(page):
                failures.append(f"{display(page)}: decoded PNG bytes duplicate {previous_pixels}")


def validate_sitemap(
    pages: list[Path], case_modified_dates: dict[str, str], failures: list[str]
) -> None:
    sitemap = ROOT / "sitemap.xml"
    try:
        root = ET.parse(sitemap).getroot()
    except (ET.ParseError, OSError) as error:
        failures.append(f"sitemap.xml: not parseable XML: {error}")
        return
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    if root.tag != f"{namespace}urlset":
        failures.append("sitemap.xml: root must be the sitemap urlset element")
    url_nodes = root.findall(f"{namespace}url")
    locations: list[str] = []
    sitemap_dates: dict[str, str] = {}
    for node in url_nodes:
        location_nodes = node.findall(f"{namespace}loc")
        location = (location_nodes[0].text or "").strip() if len(location_nodes) == 1 else ""
        if len(location_nodes) != 1 or not location:
            failures.append("sitemap.xml: every <url> must contain exactly one non-empty <loc>")
        locations.append(location)
        lastmod_nodes = node.findall(f"{namespace}lastmod")
        if len(lastmod_nodes) != 1:
            failures.append(f"sitemap.xml: {location or '<unknown URL>'} must have exactly one <lastmod>")
            continue
        lastmod = (lastmod_nodes[0].text or "").strip()
        if parse_iso_date(lastmod) is None:
            failures.append(f"sitemap.xml: {location or '<unknown URL>'} has invalid lastmod {lastmod!r}")
            continue
        sitemap_dates[location] = lastmod
    expected = {canonical_for(page) for page in pages}
    actual = set(locations)
    for url in sorted(expected - actual):
        failures.append(f"sitemap.xml: missing public page {url}")
    for url in sorted(actual - expected):
        failures.append(f"sitemap.xml: URL does not map to a public HTML page: {url}")
    if len(locations) != len(actual):
        failures.append("sitemap.xml: duplicate <loc> entries found")
    for location, modified in sorted(case_modified_dates.items()):
        if sitemap_dates.get(location) != modified:
            failures.append(
                f"sitemap.xml: {location} lastmod must match Article dateModified {modified!r}"
            )


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
    case_modified_dates: dict[str, str] = {}
    case_pages: list[Path] = []
    for page in pages:
        resolved = page.resolve()
        validate_page(resolved, parsed_pages, failures)
        if page.parent.name == CASE_DIRECTORY:
            case_pages.append(page)
            modified = validate_case_dates(resolved, parsed_pages[resolved], failures)
            if modified is not None:
                case_modified_dates[canonical_for(page)] = modified
    validate_case_images(case_pages, parsed_pages, failures)
    validate_sitemap(pages, case_modified_dates, failures)
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
    print(
        f"PASS: validated {len(pages)} HTML pages, case dates/images, sitemap, robots.txt, "
        "local references, metadata, PNG integrity, and public-content markers."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
