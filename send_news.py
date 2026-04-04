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


def matches_keyword(title: str, summary: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{title}\n{summary}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


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
            100,
        )
        if not matches_keyword(title, summary, MATCH_KEYWORDS):
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


def source_priority(item) -> tuple[int, int, int]:
    link = item.get("link", "").lower()
    feed_title = item.get("feed_title", "").lower()
    score = 0
    if "/cn/" in link:
        score += 40
    if "ithome" in link or "it之家" in feed_title:
        score += 30
    if "36kr" in link or "ifanr" in link or "mydrivers" in link:
        score += 20
    if "huawei.com" in link:
        score += 10
    if "press release" in feed_title or "/en/" in link:
        score -= 10
    return (
        score,
        len(item.get("summary", "")),
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
