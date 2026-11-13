#!/usr/bin/env python3
"""Tests for src/watchlist.py — parsing checklist sites into CFP candidates.

Run with ``uv run python -m unittest discover -s tests -v``. Entirely offline:
the HTML fixtures are compact slices of the live pages, injected as fetch text.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "watchlist"
sys.path.insert(0, str(ROOT / "src"))

import watchlist as wl  # noqa: E402

CHECKLIST = """# Conferences to Check

Check these conferences for upcoming CFPs.

- [AI Engineer](https://ai.engineer/)
- [HumanX](https://www.humanx.co/)
* [AI Summit NYC](https://newyork.theaisummit.com/)
+ [A repeated entry](https://example.org/)
- [A repeated entry](https://example.org/)
[Not a bullet](https://ignored.example/)
- [Local only](http://localhost:8080/cfp)
- [An email](mailto:speaker@example.org)
"""


class TestParseEntries(unittest.TestCase):
    def test_only_explicit_website_bullets(self) -> None:
        entries = wl.parse_entries(CHECKLIST)
        self.assertEqual(
            entries,
            [
                {"name": "AI Engineer", "event_url": "https://ai.engineer/"},
                {"name": "HumanX", "event_url": "https://www.humanx.co/"},
                {"name": "AI Summit NYC", "event_url": "https://newyork.theaisummit.com/"},
                {"name": "A repeated entry", "event_url": "https://example.org/"},
                {"name": "Local only", "event_url": "http://localhost:8080/cfp"},
            ],
        )

    def test_real_checklist(self) -> None:
        rows = wl.parse_entries((ROOT / "input" / "conferences-to-check.md").read_text())
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["name"], "AI Engineer")


class TestCandidateLinks(unittest.TestCase):
    def test_call_for_papers_beats_speaker_nav_and_lineup(self) -> None:
        links = wl.candidate_links(
            "https://newyork.theaisummit.com/", (FIX / "aisummit-site.html").read_text()
        )
        self.assertEqual(len(links), 2)
        self.assertEqual(
            links[0][0],
            "https://newyork.theaisummit.com/conference-speakers/call-for-papers/",
        )
        self.assertEqual(links[1][0], "https://newyork.theaisummit.com/conference-speakers/submit-speaker/")

    def test_speaker_application_is_found_but_speaker_roster_is_not(self) -> None:
        links = wl.candidate_links("https://www.humanx.co/", (FIX / "humanx-site.html").read_text())
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][0], "https://www.humanx.co/europe/become-a-speaker")

    def test_empty_link_is_not_a_cfp_guess(self) -> None:
        html = '<a href="/speakers/cfp"><img alt="Event photo"></a>'
        self.assertEqual(wl.candidate_links("https://example.org", html), [])

    def test_relative_and_external_urls(self) -> None:
        html = '<a href="https://sessionize.com/my-cfp">Apply Now</a>'
        self.assertEqual(
            wl.candidate_links("https://example.org", html),
            [("https://sessionize.com/my-cfp", "Apply Now", 70)],
        )

    def test_mailto_javascript_and_fragment_are_never_candidates(self) -> None:
        for href in ("mailto:cfp@example.org", "javascript:openCfp()", "#cfp"):
            with self.subTest(href=href):
                self.assertEqual(wl.candidate_links("https://example.org", f'<a href="{href}">Call for Papers</a>'), [])


class TestPageDetails(unittest.TestCase):
    def test_json_ld_event_supplies_name_date_and_country(self) -> None:
        result = wl.resolve(
            {"name": "HumanX", "event_url": "https://www.humanx.co/"},
            fetcher=lambda url: {
                "https://www.humanx.co/": (FIX / "humanx-site.html").read_text(),
                "https://www.humanx.co/europe/become-a-speaker": (FIX / "humanx-speaker.html").read_text(),
            }[url],
        )
        self.assertEqual(result.name, "HumanX Amsterdam 2027")
        self.assertEqual(result.event_date, "2027-09-20")
        self.assertEqual(result.location, "RAI Amsterdam, Amsterdam, NL")
        self.assertEqual(result.cfp_close, "Unstated")
        self.assertEqual(result.event_url, "https://www.humanx.co/")
        self.assertFalse(result.failed)
        self.assertEqual(result.error, "")

    def test_visible_event_date_but_no_fake_close_or_venue(self) -> None:
        result = wl.resolve(
            {"name": "AI Summit", "event_url": "https://newyork.theaisummit.com/"},
            fetcher=lambda url: {
                "https://newyork.theaisummit.com/": (FIX / "aisummit-site.html").read_text(),
                "https://newyork.theaisummit.com/conference-speakers/call-for-papers/": (FIX / "aisummit-cfp.html").read_text(),
            }[url],
        )
        self.assertEqual(result.name, "The AI Summit New York")
        self.assertEqual(result.event_date, "2026-12-09")
        self.assertEqual(result.cfp_close, "Unstated")  # no close date is stated on this page
        self.assertEqual(result.location, "")  # no structured location: do not invent one

    def test_explicit_deadline_formats(self) -> None:
        for text, expected in [
            ("CFP closes December 31, 2026 at midnight", "2026-12-31"),
            ("Submissions open until 2027-01-15", "2027-01-15"),
            ("Call closes Jan. 3, 2027", "2027-01-03"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(wl._deadline(text), expected)

    def test_event_date_is_not_a_deadline(self) -> None:
        html = '<p>Join us in Berlin, December 9-10, 2026. Submissions will open soon.</p>'
        result = wl.page_details("https://example.org/cfp", html)
        self.assertEqual(result["cfp_close"], "Unstated")
        self.assertEqual(result["event_date"], "2026-12-09")

    def test_deadline_after_event_does_not_stick(self) -> None:
        html = '<title>Earlier Event</title><p>December 1-2, 2026</p><p>CFP closes January 31, 2027</p>'
        self.assertEqual(wl.page_details("https://example.org/cfp", html)["cfp_close"], "Unstated")

    def test_iso_datetime_start_date(self) -> None:
        html = '<script type="application/ld+json">{"@type":"Event","name":"My Conf","startDate":"2027-08-10T09:00:00Z","location":"Paris"}</script>'
        result = wl.page_details("https://example.org/cfp", html)
        self.assertEqual(result["event_date"], "2027-08-10")
        self.assertEqual(result["location"], "Paris")

    def test_invalid_json_ld_is_ignored_not_raised(self) -> None:
        html = '<script type="application/ld+json">{bad json}</script><title>CFP | Example Conf</title>'
        self.assertEqual(wl.page_details("https://example.org/cfp", html)["name"], "Example Conf")

    def test_schema_event_skips_incomplete_and_prefers_upcoming(self) -> None:
        html = '''<script type="application/ld+json">[
            {"@type":"Event","name":"Incomplete"},
            {"@type":"Event","name":"Past Complete","startDate":"2020-01-10"},
            {"@type":"Event","name":"Upcoming Complete","startDate":"2999-06-10"}
        ]</script>'''
        result = wl.page_details("https://example.org/cfp", html)
        self.assertEqual(result["name"], "Upcoming Complete")
        self.assertEqual(result["event_date"], "2999-06-10")

    def test_schema_event_uses_supplied_run_date(self) -> None:
        html = '''<script type="application/ld+json">[
            {"@type":"Event","name":"Edition 2026","startDate":"2026-06-10"},
            {"@type":"Event","name":"Edition 2027","startDate":"2027-06-10"},
            {"@type":"Event","name":"Edition 2030","startDate":"2030-06-10"}
        ]</script>'''
        result = wl.page_details("https://example.org/cfp", html, today="2028-01-01")
        self.assertEqual(result["name"], "Edition 2030")
        self.assertEqual(result["event_date"], "2030-06-10")

    def test_cfp_deadline_is_not_reused_as_event_date(self) -> None:
        html = '''<h1>CFP closes January 15, 2027</h1>
                  <p>Example Conf takes place June 10-11, 2027.</p>'''
        result = wl.page_details("https://example.org/cfp", html)
        self.assertEqual(result["cfp_close"], "2027-01-15")
        self.assertEqual(result["event_date"], "2027-06-10")

        only_deadline = wl.page_details("https://example.org/cfp", "<h1>CFP closes January 15, 2027</h1>")
        self.assertEqual(only_deadline["cfp_close"], "2027-01-15")
        self.assertEqual(only_deadline["event_date"], "TBA")

    def test_registration_close_is_not_a_cfp_or_event_date(self) -> None:
        for wording in ("Registration closes December 1, 2026", "Registration deadline: December 1, 2026"):
            with self.subTest(wording=wording):
                result = wl.page_details("https://example.org/cfp", f"<p>{wording}</p>")
                self.assertEqual(result["cfp_close"], "Unstated")
                self.assertEqual(result["event_date"], "TBA")

    def test_generic_cfp_title_suffix_does_not_replace_conference_name(self) -> None:
        html = "<title>Example Conf | Call for Papers</title>"
        result = wl.page_details("https://example.org/cfp", html, fallback_name="Example Conf")
        self.assertEqual(result["name"], "Example Conf")

    def test_generic_cfp_title_with_year_does_not_replace_conference_name(self) -> None:
        html = "<title>Call for Papers 2027 | HumanX Amsterdam 2027</title>"
        result = wl.page_details("https://example.org/cfp", html, fallback_name="HumanX")
        self.assertEqual(result["name"], "HumanX Amsterdam 2027")

    def test_explicit_closed_markers(self) -> None:
        for text in (
            "<h1>Applications Closed</h1>",
            "<h1>CFP is closed</h1>",
            "<h1>CFP has been closed</h1>",
            "<h1>CFP has now been closed</h1>",
            "<h1>Call for Papers has now closed</h1>",
            "<h1>Call for Papers has been closed</h1>",
            "<h1>Speaker submissions closed</h1>",
            "<h1>Submissions are now closed</h1>",
            "<h1>Submissions have been closed</h1>",
        ):
            with self.subTest(text=text):
                self.assertTrue(wl.page_details("https://example.org/cfp", text)["closed"])

    def test_open_dates_and_negations_are_not_closed_markers(self) -> None:
        for text in (
            "<h1>CFP is not closed</h1>",
            "<h1>CFP has not been closed</h1>",
            "<h1>CFP has not yet been closed</h1>",
            "<h1>Submissions are not closed</h1>",
            "<h1>Submissions have not been closed</h1>",
            "<h1>Submissions will not be closed</h1>",
            "<h1>Applications close on January 3, 2027</h1>",
            "<h1>Now Accepting Submissions</h1>",
        ):
            with self.subTest(text=text):
                self.assertFalse(wl.page_details("https://example.org/cfp", text)["closed"])

    def test_deadline_check_keeps_unstated_and_same_day_open(self) -> None:
        self.assertFalse(wl.deadline_before_today("Unstated", today="2026-11-12"))
        self.assertFalse(wl.deadline_before_today("2026-11-12", today="2026-11-12"))
        self.assertFalse(wl.deadline_before_today("2026-11-13", today="2026-11-12"))
        self.assertTrue(wl.deadline_before_today("2026-11-11", today="2026-11-12"))


class TestResolveAndCache(unittest.TestCase):
    def test_no_candidate_is_reported_not_fabricated(self) -> None:
        result = wl.resolve(
            {"name": "No CFP", "event_url": "https://example.org/"},
            fetcher=lambda _url: (FIX / "no-cfp.html").read_text(),
        )
        self.assertEqual(result.cfp_url, "")
        self.assertIn("no explicit", result.error)
        self.assertFalse(result.failed)

    def _site(self, html: str):
        return lambda url: '<a href="/cfp">Call for Papers</a>' if url == "https://example.org/" else html

    def test_closed_top_candidate_falls_through_to_current_candidate(self) -> None:
        site = '<a href="/old-cfp">Call for Papers</a><a href="/current-cfp">Call for Papers</a>'
        pages = {
            "https://example.org/old-cfp": "<h1>CFP has been closed</h1>",
            "https://example.org/current-cfp": '''<title>Example Conf | Call for Papers</title>
                <p>Example Conf takes place June 10-11, 2027.</p>''',
        }
        calls = []

        def fetch(url):
            calls.append(url)
            return site if url == "https://example.org/" else pages[url]

        result = wl.resolve(
            {"name": "Example Conf", "event_url": "https://example.org/"},
            fetcher=fetch, today="2026-11-12",
        )
        self.assertEqual(result.cfp_url, "https://example.org/current-cfp")
        self.assertEqual(result.name, "Example Conf")
        self.assertEqual(result.event_date, "2027-06-10")
        self.assertEqual(result.error, "")
        self.assertFalse(result.failed)
        self.assertEqual(calls, ["https://example.org/", *pages])

    def test_broken_top_candidate_falls_through_to_valid_candidate(self) -> None:
        site = '<a href="/broken-cfp">Call for Papers</a><a href="/valid-cfp">Apply to Speak</a>'

        def fetch(url):
            if url == "https://example.org/":
                return site
            if url == "https://example.org/broken-cfp":
                raise TimeoutError("first candidate timed out")
            return "<h1>Call for Papers</h1>"

        result = wl.resolve(
            {"name": "Example Conf", "event_url": "https://example.org/"},
            fetcher=fetch, today="2026-11-12",
        )
        self.assertEqual(result.cfp_url, "https://example.org/valid-cfp")
        self.assertEqual(result.error, "")
        self.assertFalse(result.failed)

    def test_candidate_fetches_are_bounded_and_total_failure_is_failed(self) -> None:
        site = "".join(f'<a href="/cfp-{number}">Call for Papers</a>' for number in range(1, 5))
        calls = []

        def fetch(url):
            calls.append(url)
            if url == "https://example.org/":
                return site
            raise TimeoutError(f"could not fetch {url}")

        result = wl.resolve(
            {"name": "Down", "event_url": "https://example.org/"},
            fetcher=fetch, today="2026-11-12",
        )
        self.assertTrue(result.failed)
        self.assertIn("TimeoutError", result.error)
        self.assertEqual(result.cfp_url, "")
        self.assertEqual(
            calls,
            ["https://example.org/"] + [f"https://example.org/cfp-{number}" for number in range(1, 4)],
        )

    def test_explicitly_closed_page_does_not_create_a_cfp(self) -> None:
        html = '<h1>Applications Closed</h1><p>The event is December 9-10, 2026.</p>'
        result = wl.resolve(
            {"name": "Closed", "event_url": "https://example.org/"},
            fetcher=self._site(html), today="2026-11-12",
        )
        self.assertIn("explicitly closed", result.error)
        self.assertFalse(result.failed)
        self.assertEqual(result.cfp_url, "https://example.org/cfp")

    def test_past_deadline_is_skipped_even_without_applications_closed_text(self) -> None:
        html = '<h1>CFP closes October 1, 2026</h1><p>Conference December 9-10, 2026</p>'
        result = wl.resolve(
            {"name": "Past", "event_url": "https://example.org/"},
            fetcher=self._site(html), today="2026-11-12",
        )
        self.assertIn("closed 2026-10-01", result.error)

    def test_deadline_today_is_not_skipped(self) -> None:
        html = '<h1>CFP closes November 12, 2026</h1><p>Conference December 9-10, 2026</p>'
        result = wl.resolve(
            {"name": "Open Today", "event_url": "https://example.org/"},
            fetcher=self._site(html), today="2026-11-12",
        )
        self.assertEqual(result.cfp_close, "2026-11-12")
        self.assertEqual(result.error, "")

    def test_invalid_today_is_reported(self) -> None:
        result = wl.resolve(
            {"name": "Invalid", "event_url": "https://example.org/"},
            fetcher=self._site(""), today="2026-11-32",
        )
        self.assertTrue(result.failed)
        self.assertIn("ValueError", result.error)

    def test_fetch_failure_is_distinguishable_from_no_candidate(self) -> None:
        def down(_url):
            raise TimeoutError("timed out")

        result = wl.resolve({"name": "Down", "event_url": "https://example.org"}, fetcher=down)
        self.assertTrue(result.failed)
        self.assertIn("timed out", result.error)

    def test_optional_cache_supplies_keys_and_store_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            faked = {"https://example.org": '<a href="/cfp">Apply Now</a>'}
            call_count = 0

            def once(url):
                nonlocal call_count
                call_count += 1
                return faked[url]

            # A live fetch populates the cache; offline mode reads it explicitly.
            first = wl._cache_fetch("https://example.org", cache, fetcher=once)
            cached = first
            self.assertTrue(list(cache.glob("*.html")))
            second = wl._cache_fetch("https://example.org", cache, fetcher=once, offline=True)
            self.assertEqual(first, cached)
            # Explicit faking only here: second call reads the known cache.
            self.assertEqual(second, first)
            self.assertEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
