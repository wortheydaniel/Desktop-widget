from datetime import datetime, timedelta, timezone

from cachy_widget import news

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Big &amp; bold &lt;b&gt;news&lt;/b&gt;</title><link>https://a.example/1</link>
<pubDate>Fri, 02 Oct 2026 12:00:00 GMT</pubDate></item>
<item><title>Bad link</title><link>javascript:alert(1)</link></item>
<item><title>Second</title><link>https://a.example/2</link></item>
</channel></rss>"""

ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom story</title>
<link rel="alternate" href="https://b.example/x"/><updated>2026-10-02T11:00:00Z</updated></entry></feed>"""


def test_rss_parse_cleans_and_filters():
    items = news.parse_feed(RSS, "A")
    assert [i.title for i in items] == ["Big & bold news", "Second"]  # js: link dropped
    assert items[0].published == datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


def test_atom_parse():
    (item,) = news.parse_feed(ATOM, "B")
    assert item.link == "https://b.example/x" and item.published.hour == 11


def test_merge_round_robin_and_dedupe():
    a = news.parse_feed(RSS, "A")
    b = news.parse_feed(ATOM, "B") + [news.Headline("B", "second", "https://b.example/dup", None)]
    merged = news.merge([a, b], 4)
    assert [h.title for h in merged] == ["Big & bold news", "Atom story", "Second"]


def test_time_ago():
    now = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
    assert news.time_ago(now - timedelta(minutes=5), now) == "5m ago"
    assert news.time_ago(now - timedelta(hours=3), now) == "3h ago"
    assert news.time_ago(None) == ""
