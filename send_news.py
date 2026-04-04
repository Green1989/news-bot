import html
import os
import re
from calendar import timegm
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup


FEISHU_WEBHOOK = os.environ["FEISHU_WEBHOOK"]
MAX_ITEMS_PER_FEED = int(os.getenv("MAX_ITEMS_PER_FEED", "2"))
MAX_TOTAL_ITEMS = int(os.getenv("MAX_TOTAL_ITEMS", "8"))
FEEDS_FILE = os.getenv("FEEDS_FILE", "feeds.txt")
KEYWORD = os.getenv("FEISHU_KEYWORD", "华为")
MAX_ITEM_AGE_DAYS = int(os.getenv("MAX_ITEM_AGE_DAYS", "1"))
MATCH_KEYWORDS = [
    keyword.strip()
    for keyword in os.getenv("FEISHU_MATCH_KEYWORDS", KEYWORD).split(",")
    if keyword.strip()
]
TITLE_STOPWORDS = ("huawei", "华为")


def clean_text(text: str, limit: int = 140) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


MIN_RELEVANCE_SCORE = int(os.getenv("MIN_RELEVANCE_SCORE", "30"))

TITLE_MATCH_SCORE = 30
SUMMARY_MATCH_SCORE = 10
PER_EXTRA_MATCH = 5
EXTRA_MATCH_CAP = 15


def _match_score(count: int, base: int) -> int:
    if count == 0:
        return 0
    return base + min((count - 1) * PER_EXTRA_MATCH, EXTRA_MATCH_CAP)


def relevance_score(title: str, summary: str, keywords: list[str]) -> int:
    if not keywords:
        return 100
    title_lower = title.lower()
    summary_lower = summary.lower()
    title_count = sum(title_lower.count(kw.lower()) for kw in keywords)
    summary_count = sum(summary_lower.count(kw.lower()) for kw in keywords)
    return _match_score(title_count, TITLE_MATCH_SCORE) + _match_score(
        summary_count, SUMMARY_MATCH_SCORE
    )


def load_feeds(path: str):
    feeds = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if url and not url.startswith("#"):
                feeds.append(url)
    return feeds


def parse_entry_published_at(entry):
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed_time:
        return None
    return datetime.fromtimestamp(timegm(parsed_time), tz=timezone.utc)


def is_recent(published_at: datetime | None) -> bool:
    if published_at is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ITEM_AGE_DAYS)
    return published_at >= cutoff


def fetch_items(feed_url: str):
    parsed = feedparser.parse(feed_url)
    items = []
    feed_title = parsed.feed.get("title", feed_url)

    for entry in parsed.entries:
        published_at = parse_entry_published_at(entry)
        if not is_recent(published_at):
            continue

        title = clean_text(entry.get("title", "无标题"), 80)
        summary = clean_text(
            entry.get("summary", "") or entry.get("description", ""),
            200,
        )
        if relevance_score(title, summary, MATCH_KEYWORDS) < MIN_RELEVANCE_SCORE:
            continue

        link = entry.get("link", "")
        items.append(
            {
                "feed_title": feed_title,
                "title": title,
                "summary": summary,
                "link": link,
                "published_at": published_at,
            }
        )

        if len(items) >= MAX_ITEMS_PER_FEED:
            break

    return items


def normalize_title(title: str) -> str:
    text = title.lower()
    for word in TITLE_STOPWORDS:
        text = text.replace(word, "")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


def story_key(item) -> str:
    path = urlparse(item.get("link", "")).path.rstrip("/")
    slug = path.split("/")[-1] if path else ""
    if slug and slug.lower().endswith(".html"):
        return f"slug:{slug[:-5].lower()}"
    normalized_title = normalize_title(item.get("title", ""))
    return f"title:{normalized_title[:40]}"


SOURCE_WEIGHTS = [
    (40, ("huawei.com/cn",)),
    (30, ("ithome", "36kr", "ifanr", "mydrivers")),
    (20, ("huaweicentral", "phonearena")),
    (10, ("news.google",)),
]


def source_type_weight(link: str, feed_title: str) -> int:
    link_lower = link.lower()
    for weight, domains in SOURCE_WEIGHTS:
        if any(d in link_lower for d in domains):
            return weight
    if "/en/" in link_lower:
        return -10
    return 0


def summary_length_bonus(summary_text: str) -> int:
    length = len(summary_text)
    if length >= 150:
        return 20
    if length >= 50:
        return 10
    return 0


def source_priority(item) -> tuple[int, int]:
    link = item.get("link", "")
    feed_title = item.get("feed_title", "")
    quality_score = source_type_weight(link, feed_title) + summary_length_bonus(
        item.get("summary", "")
    )
    return (
        quality_score,
        int(published_sort_value(item)),
    )


def deduplicate_items(items):
    best_items = {}
    for item in items:
        key = story_key(item)
        current = best_items.get(key)
        if current is None or source_priority(item) > source_priority(current):
            best_items[key] = item
    return sorted(
        best_items.values(),
        key=published_sort_value,
        reverse=True,
    )


def published_sort_value(item) -> float:
    published_at = item.get("published_at")
    if hasattr(published_at, "timestamp"):
        return published_at.timestamp()
    return float(published_at or 0)


def build_message(all_items):
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"{KEYWORD}早报 {today}", ""]

    for idx, item in enumerate(all_items, start=1):
        lines.append(f"{idx}. [{item['feed_title']}] {item['title']}")
        if item["summary"]:
            lines.append(f"   {item['summary']}")
        if item["link"]:
            lines.append(f"   {item['link']}")
        lines.append("")

    return "\n".join(lines).strip()


def send_to_feishu(text: str):
    payload = {"msg_type": "text", "content": {"text": text}}
    resp = requests.post(
        FEISHU_WEBHOOK,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Feishu webhook error: {data}")


def main():
    feeds = load_feeds(FEEDS_FILE)
    all_items = []

    for feed in feeds:
        try:
            items = fetch_items(feed)
            all_items.extend(items)
        except Exception as e:
            print(f"[WARN] failed to parse {feed}: {e}")

    all_items = deduplicate_items(all_items)
    all_items = all_items[:MAX_TOTAL_ITEMS]

    if not all_items:
        text = f"{KEYWORD}早报\n今天没有抓到与{KEYWORD}相关的内容。"
    else:
        text = build_message(all_items)

    print(text)
    send_to_feishu(text)


if __name__ == "__main__":
    main()
