"""Discover CFP links from a Markdown checklist of conference websites.

The input is intentionally a *checklist*, not a CFP table::

    - [HumanX](https://www.humanx.co/)

Only these explicit links are checked; the module never uses external search or
invents CFP paths. For each conference site it picks one likely speaker
submission link, then reads that page for Schema.org ``Event`` metadata and
explicit deadline text. Generic speaker line-ups are not treated as CFP pages.

This is deliberately conservative: an unstated CFP close stays ``Unstated``,
and an event date not present in a structured event or displayed on the page
stays ``TBA``. A page explicitly closed for submissions, or a stated close
before ``today``, is reported as non-eligible rather than written as a new CFP.
``fetcher`` is injectable so parsing is tested offline.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from cfp_writer import parse_start_date

_ENTRY_RE = re.compile(
    r"^\s*[-*+]\s+\[([^\]]+)\]\((\s*<?https?://[^)\s>]+>?)(?:\s+[\"'][^)]*)?\)\s*$",
    re.IGNORECASE,
)
_MONTH_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+"
    r"\d{1,2}(?:\s*[–—-]\s*\d{1,2})?,?\s*(?:19|20)\d{2}",
    re.IGNORECASE,
)
_DEADLINE_RE = re.compile(
    r"(?:deadline|due\s+date|closes?|closing\s+date|apply\s+by|"
    r"submissions?\s+(?:open\s+)?(?:until|until:)|cfp\s+(?:closes?|until))",
    re.IGNORECASE,
)
# Match an explicit submission-state close, not an upcoming date with "closes".
# "CFP is not closed" / "Submissions are not closed" must not match.
_CLOSED_RE = re.compile(
    r"\b(?:"
    r"(?:speaker\s+)?(?:cfp|call\s+for\s+(?:papers?|proposals?|speakers?))\s+"
    r"(?:is\s+|has\s+)?(?:now\s+)?closed\b"
    r"|(?:applications?|submissions?)\s+(?:are\s+|is\s+|has\s+|have\s+)?(?:now\s+)?closed\b"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CfpResult:
    name: str
    event_url: str
    cfp_url: str = ""
    event_date: str = "TBA"
    location: str = ""
    cfp_close: str = "Unstated"
    error: str = ""
    # A fetch failure means "could not check", not "no CFP exists". This is
    # important downstream: it must not let an incomplete manifest archive notes.
    failed: bool = False


def parse_entries(text: str) -> list[dict]:
    """Read only ``- [Name](https://event/)`` bullets, preserving file order.

    Table cells, ordinary links in prose, headings and other bullets do not
    quietly turn into websites to crawl. This is important because manual input
    files are explicitly selected: a checklist is opt-in, not an invitation to
    follow every link mentioned in an email.
    """
    entries = []
    seen = set()
    for line in (text or "").splitlines():
        m = _ENTRY_RE.fullmatch(line.strip())
        if not m:
            continue
        name, url = m.group(1).strip(), m.group(2).strip().strip("<>")
        if name and url and (name, url) not in seen:
            seen.add((name, url))
            entries.append({"name": name, "event_url": url})
    return entries


class _PageParser(HTMLParser):
    """Extract links, JSON-LD, meta descriptions and visible text from a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.json_ld: list[dict | list] = []
        self.descriptions: list[str] = []
        self.title: str = ""
        self._href: str | None = None
        self._link_text: list[str] = []
        self._json: list[str] | None = None
        self._skip = 0  # style/script/template content must never resemble event data
        self._in_title = False
        self._visible: list[str] = []
        self._title_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = dict(attrs)
        if tag in ("script", "style", "template", "noscript"):
            self._skip += 1
            if tag == "script" and a.get("type", "").lower() == "application/ld+json":
                self._json = []
        if self._skip:
            return
        if tag == "a":
            self._href = a.get("href")
            self._link_text = []
        elif tag == "meta" and a.get("name", "").lower() == "description":
            self.descriptions.append(a.get("content", ""))
        elif tag == "title":
            self._in_title = True
            self._title_text = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style", "template", "noscript"):
            self._skip -= 1
            self._skip = max(self._skip, 0)  # malformed HTML must not hide content
        if tag == "script" and self._json is not None:
            raw = "".join(self._json).strip()
            if raw:
                try:
                    self.json_ld.append(json.loads(raw))
                except (ValueError, json.JSONDecodeError):
                    pass  # a malformed vendor script is not a structural failure
            self._json = None
        if tag == "a" and self._href is not None:
            label = " ".join(" ".join(self._link_text).split())
            self.links.append((self._href.strip(), label))
            self._href = None
            self._link_text = []
        if tag == "title":
            self._in_title = False
            self.title = " ".join(" ".join(self._title_text).split())

    def handle_data(self, data):
        if self._json is not None:
            self._json.append(data)
            return
        if self._skip:
            return
        if self._href is not None:
            self._link_text.append(data)
        if self._in_title:
            self._title_text.append(data)
        if data.strip():
            self._visible.append(data.strip())

    @property
    def visible_text(self) -> str:
        return " ".join(self._visible)


def _link_score(href: str, label: str) -> int:
    """Positive when a link is likely a CFP, rather than a speaker line-up.

    Link text is trusted more than a URL fragment. ``speakers/arsh-arora`` is
    not a CFP just because it contains ``speaker``; ``Apply to Speak`` and
    ``call-for-papers`` are explicit submission intents. Empty-icon links are
    not guessed at: blindly following every link would crawl a whole website.
    """
    href_l = href.lower().split("#", 1)[0]
    text = " ".join(label.lower().replace("_", " ").replace("-", " ").split())
    url = " ".join(re.sub(r"[^a-z0-9]+", " ", href_l).split())
    if not text or href_l.startswith(("javascript:", "mailto:", "#")):
        return -1
    if any(word in text for word in ("past speakers", "past editions", "watch video")):
        return -1
    if re.search(r"\b(call for|apply|submit|proposal|papers?)\b", text + " " + url):
        if re.search(r"\b(call for|apply|submit|proposal|papers?)\b", text):
            if re.search(r"\b(call for (papers?|proposals?|participation)|"
                         r"apply to speak|become a speaker|speaker application)\b", text):
                return 100
            if re.search(r"\b(apply|submit)\b", text):
                return 70
            if re.search(r"\bcfp\b", text):
                return 90
        return 55
    if re.search(r"\bcfp\b", text):
        return 80
    return -1


def candidate_links(page_url: str, html: str) -> list[tuple[str, str, int]]:
    """Return absolute CFP candidates as ``(url, link text, score)``, best first."""
    p = _PageParser()
    p.feed(html)
    candidates = []
    for href, label in p.links:
        raw = href.strip().lower()
        if raw.startswith(("#", "javascript:", "mailto:")):
            continue  # URL-joining a #fragment makes it look like a new HTTP URL.
        url = urljoin(page_url, href)
        if urlsplit(url).scheme not in ("http", "https"):
            continue
        score = _link_score(url, label)
        if score >= 0:
            candidates.append((url, label, score))
    # Python's sort is stable: equal scores preserve website link order.
    return sorted(candidates, key=lambda item: -item[2])


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _iso_date(value) -> str:
    """Accept a clean ISO date or the date part of an ISO datetime."""
    match = re.match(r"^\s*(\d{4}-\d{2}-\d{2})", str(value or ""))
    if not match:
        return ""
    try:
        return date.fromisoformat(match.group(1)).isoformat()
    except ValueError:
        return ""


def _schema_event(parser: _PageParser) -> dict:
    """Prefer a fully identifiable upcoming Event from Schema.org JSON-LD."""
    for root in parser.json_ld:
        for obj in _walk_json(root):
            types = obj.get("@type", "")
            if isinstance(types, str):
                types = [types]
            if "Event" not in types:
                continue
            start = _iso_date(obj.get("startDate"))
            if obj.get("name") and start:
                return {"startDate": start, **obj}
            return obj  # Structured name/location is still useful without a date.
    return {}


def _event_location(event: dict) -> str:
    """A venue/city/country string from Schema.org, without guessing a format."""
    locations = event.get("location", [])
    if isinstance(locations, (dict, str)):
        locations = [locations]
    for location in locations:
        if isinstance(location, str):
            if location.strip():
                return location.strip()
            continue
        if not isinstance(location, dict):
            continue
        venue = str(location.get("name", "") or "").strip()
        address = location.get("address", {})
        if isinstance(address, str):
            return ", ".join(x for x in (venue, address) if x)
        if not isinstance(address, dict):
            address = {}
        city = str(address.get("addressLocality", "") or "").strip()
        region = str(address.get("addressRegion", "") or "").strip()
        country = str(address.get("addressCountry", "") or "").strip()
        part = ", ".join(x for x in (city or region, country) if x)
        if venue and part:
            return f"{venue}, {part}"
        return venue or part
    return ""


def _deadline(text: str) -> str:
    """Read a stated close only when deadline wording sits next to a date.

    Dates anywhere else on an event page (the conference dates, copyright year,
    old workshops) must not become the CFP deadline. Rubber-stamping the first
    date found is why this function deliberately takes the small surrounding
    window instead of scanning the whole document.
    """
    for match in _DEADLINE_RE.finditer(text):
        nearby = text[match.end(): match.end() + 180]
        iso = _iso_date(nearby)
        if iso:
            return iso
        natural = _MONTH_DATE_RE.search(nearby)
        if natural:
            parsed = parse_start_date(natural.group(0))
            if parsed:
                return parsed
    return ""


def deadline_before_today(cfp_close: str, today=None) -> bool:
    """True only for a valid ISO close strictly before the effective day.

    Free-text ``Unstated`` is not a canceled CFP. An invalid ``--today`` fails
    resolution rather than quietly making a stale historical page eligible.
    """
    closing = _iso_date(cfp_close)
    if not closing:
        return False
    if today is None:
        current = date.today()
    elif isinstance(today, date):
        current = today
    else:
        current = date.fromisoformat(str(today))
    return closing < current.isoformat()


def page_details(cfp_url: str, html: str, fallback_name: str = "") -> dict:
    """Extract CFP/event details from one candidate page."""
    p = _PageParser()
    p.feed(html)
    event = _schema_event(p)
    start = _iso_date(event.get("startDate"))
    if not start:
        # Readable event dates in concise meta copy and visible page copy are a
        # weaker signal than JSON-LD, but a normal conference footer is useful.
        for text in [*p.descriptions, p.visible_text]:
            found = _MONTH_DATE_RE.search(text)
            if found:
                start = parse_start_date(found.group(0))
                if start:
                    break
    name = str(event.get("name") or "").strip()
    if not name:
        title = p.title or fallback_name
        name = re.split(r"\s+[|–—]\s+", title)[-1].strip() or fallback_name
    deadline = _deadline(f"{p.title} {p.visible_text}")
    if deadline and start and deadline > start:
        # A stated close after the conference date cannot be this event's close.
        deadline = ""
    closed = _CLOSED_RE.search(f"{p.title} {p.visible_text}")
    return {
        "name": name,
        "event_url": "",
        "cfp_url": cfp_url,
        "event_date": start or "TBA",
        "location": _event_location(event),
        "cfp_close": deadline or "Unstated",
        "closed": bool(closed),  # an explicit status, unlike "not yet stated"
    }


def fetch_url(url: str, timeout: int = 25) -> str:
    """Fetch a public event page as text, without requests/JS or browser state."""
    request = urllib.request.Request(url, headers={"User-Agent": "cfp-watchlist/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _cache_fetch(url: str, cache: Path | None = None, fetcher=None) -> str:
    """Read an explicitly supplied HTML cache first, then fetch live."""
    target = cache / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".html") if cache else None
    if target is not None and target.is_file():
        return target.read_text(encoding="utf-8")
    text = (fetcher or fetch_url)(url)
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return text


def resolve(entry: dict, fetcher=None, cache: Path | None = None, today=None) -> CfpResult:
    """Resolve one checklist entry to a CFP candidate and its known details.

    No candidate, script-only rendering, or failing page returns a result with
    a diagnostic ``error`` rather than an empty/fake CFP URL. The caller skips
    such results but prints them, so a checklist never claims undated guesses.
    """
    name = str(entry.get("name", "") or "").strip()
    event_url = str(entry.get("event_url", "") or "").strip()
    fetch = fetcher or (lambda url: _cache_fetch(url, cache))
    try:
        if today is not None and not isinstance(today, date):
            date.fromisoformat(str(today))  # validate a caller's --today even on a failed site
        html = fetch(event_url)
        candidates = candidate_links(event_url, html)
        if not candidates:
            return CfpResult(name, event_url, error="no explicit speaker-submission link")
        chosen, _label, _score = candidates[0]
        result = page_details(chosen, fetch(chosen), fallback_name=name)
        result["event_url"] = event_url
        if not result["name"]:
            result["name"] = name
        # A permanent past CFP URL is evidence of a historical submission page,
        # not of an open CFP. Explicit close wording wins even when no deadline
        # is stated on the page. With a date, closing today remains eligible,
        # matching the other sources' >= today convention.
        details = dict(result)
        explicitly_closed = details.pop("closed")
        if explicitly_closed or deadline_before_today(details["cfp_close"], today):
            reason = (
                f"CFP is explicitly closed: {chosen}"
                if explicitly_closed
                else f"CFP closed {details['cfp_close']}: {chosen}"
            )
            return CfpResult(**details, error=reason)
        return CfpResult(**details)
    except Exception as exc:
        return CfpResult(name, event_url, error=f"{type(exc).__name__}: {exc}", failed=True)
