"""Headlines: RSS 2.0 / Atom parsing and a round-robin merge across feeds."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from . import net

_TAG = re.compile(r"<[^>]+>")


@dataclass
class Headline:
    source: str
    title: str
    link: str
    published: datetime | None  # tz-aware UTC when known


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean(text: str | None) -> str:
    return " ".join(html.unescape(_TAG.sub("", text or "")).split())


def _when(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)  # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))  # Atom: ISO 8601
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_link(link: str | None) -> str:
    link = (link or "").strip()
    return link if link.lower().startswith(("http://", "https://")) else ""


def parse_feed(data: bytes, source: str) -> list[Headline]:
    root = ET.fromstring(data)
    out: list[Headline] = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        fields: dict[str, str | None] = {}
        for child in node:
            name = _local(child.tag)
            if name == "link":
                # Atom: <link href=…>; RSS: <link>text</link>. Prefer rel=alternate.
                href = child.get("href")
                if href and child.get("rel", "alternate") == "alternate":
                    fields["link"] = href
                elif not href and "link" not in fields:
                    fields["link"] = child.text
            elif name in ("title", "pubDate", "published", "updated") and name not in fields:
                fields[name] = child.text
        title = _clean(fields.get("title"))
        link = _safe_link(fields.get("link"))
        if title and link:
            published = _when(fields.get("pubDate") or fields.get("published") or fields.get("updated"))
            out.append(Headline(source, title, link, published))
    return out


def fetch_feed(feed: dict) -> list[Headline]:
    return parse_feed(net.get(feed["url"], timeout=12), feed["name"])


def merge(per_feed: list[list[Headline]], count: int) -> list[Headline]:
    """Round-robin across feeds (each already in its own editorial order), dropping near-duplicates."""
    seen: set[str] = set()
    out: list[Headline] = []
    queues = [list(q) for q in per_feed]
    while len(out) < count and any(queues):
        for q in queues:
            while q:
                h = q.pop(0)
                key = re.sub(r"\W+", "", h.title.lower())[:48]
                if key not in seen:
                    seen.add(key)
                    out.append(h)
                    break
            if len(out) >= count:
                break
    return out


def gather(feeds: list[dict], count: int) -> tuple[list[Headline], list[str]]:
    """Fetch every feed; return (headlines, error messages). Fails only if all feeds fail."""
    results, errors = [], []
    for feed in feeds:
        try:
            results.append(fetch_feed(feed))
        except Exception as exc:  # noqa: BLE001 - one bad feed must not blank the widget
            errors.append(f"{feed.get('name', feed.get('url'))}: {exc}")
    if not results:
        raise RuntimeError("; ".join(errors) or "no feeds configured")
    return merge(results, count), errors


def time_ago(dt: datetime | None, now: datetime | None = None) -> str:
    if dt is None:
        return ""
    secs = ((now or datetime.now(timezone.utc)) - dt).total_seconds()
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"
