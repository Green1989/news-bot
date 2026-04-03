import importlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


os.environ.setdefault("FEISHU_WEBHOOK", "https://example.com/webhook")
sys.modules.setdefault("feedparser", SimpleNamespace(parse=None))
sys.modules.setdefault("requests", SimpleNamespace(post=None))
sys.modules.setdefault(
    "bs4",
    SimpleNamespace(
        BeautifulSoup=lambda text, parser: SimpleNamespace(
            get_text=lambda separator, strip: text
        )
    ),
)

send_news = importlib.import_module("send_news")


class FetchItemsTests(unittest.TestCase):
    def test_fetch_items_matches_any_configured_keyword_alias(self):
        parsed = SimpleNamespace(
            feed={"title": "Tech Feed"},
            entries=[
                {
                    "title": "Huawei launches new cloud service",
                    "summary": "Enterprise rollout expands in Europe",
                    "link": "https://example.com/huawei-en",
                },
                {
                    "title": "OpenAI 发布新模型",
                    "summary": "这条是人工智能行业新闻",
                    "link": "https://example.com/openai",
                },
            ],
        )

        with (
            patch.object(send_news, "MATCH_KEYWORDS", ["华为", "Huawei"]),
            patch.object(send_news.feedparser, "parse", return_value=parsed),
        ):
            items = send_news.fetch_items("https://example.com/rss")

        self.assertEqual(
            [item["title"] for item in items],
            ["Huawei launches new cloud service"],
        )

    def test_fetch_items_only_returns_entries_matching_keyword(self):
        parsed = SimpleNamespace(
            feed={"title": "Tech Feed"},
            entries=[
                {
                    "title": "华为发布新芯片",
                    "summary": "公司带来新产品进展",
                    "link": "https://example.com/huawei",
                },
                {
                    "title": "OpenAI 发布新模型",
                    "summary": "这条是人工智能行业新闻",
                    "link": "https://example.com/openai",
                },
            ],
        )

        with (
            patch.object(send_news, "MATCH_KEYWORDS", ["华为"]),
            patch.object(send_news.feedparser, "parse", return_value=parsed),
        ):
            items = send_news.fetch_items("https://example.com/rss")

        self.assertEqual([item["title"] for item in items], ["华为发布新芯片"])

    def test_fetch_items_scans_past_non_matching_entries_to_fill_limit(self):
        parsed = SimpleNamespace(
            feed={"title": "Tech Feed"},
            entries=[
                {
                    "title": "今日 AI 简讯",
                    "summary": "人工智能行业动态",
                    "link": "https://example.com/1",
                },
                {
                    "title": "开源社区动态",
                    "summary": "开源项目版本更新",
                    "link": "https://example.com/2",
                },
                {
                    "title": "华为云发布新服务",
                    "summary": "云业务更新",
                    "link": "https://example.com/3",
                },
                {
                    "title": "供应链关注华为新机",
                    "summary": "市场继续讨论新品",
                    "link": "https://example.com/4",
                },
            ],
        )

        with (
            patch.object(send_news, "MATCH_KEYWORDS", ["华为"]),
            patch.object(send_news.feedparser, "parse", return_value=parsed),
        ):
            items = send_news.fetch_items("https://example.com/rss")

        self.assertEqual(
            [item["title"] for item in items],
            ["华为云发布新服务", "供应链关注华为新机"],
        )


if __name__ == "__main__":
    unittest.main()
