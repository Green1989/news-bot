import importlib
import os
import sys
import time
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
        recent = time.gmtime(time.time() - 2 * 60 * 60)
        parsed = SimpleNamespace(
            feed={"title": "Tech Feed"},
            entries=[
                {
                    "title": "Huawei launches new cloud service",
                    "summary": "Enterprise rollout expands in Europe",
                    "link": "https://example.com/huawei-en",
                    "published_parsed": recent,
                },
                {
                    "title": "OpenAI 发布新模型",
                    "summary": "这条是人工智能行业新闻",
                    "link": "https://example.com/openai",
                    "published_parsed": recent,
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
        recent = time.gmtime(time.time() - 2 * 60 * 60)
        parsed = SimpleNamespace(
            feed={"title": "Tech Feed"},
            entries=[
                {
                    "title": "华为发布新芯片",
                    "summary": "公司带来新产品进展",
                    "link": "https://example.com/huawei",
                    "published_parsed": recent,
                },
                {
                    "title": "OpenAI 发布新模型",
                    "summary": "这条是人工智能行业新闻",
                    "link": "https://example.com/openai",
                    "published_parsed": recent,
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
        recent = time.gmtime(time.time() - 2 * 60 * 60)
        parsed = SimpleNamespace(
            feed={"title": "Tech Feed"},
            entries=[
                {
                    "title": "今日 AI 简讯",
                    "summary": "人工智能行业动态",
                    "link": "https://example.com/1",
                    "published_parsed": recent,
                },
                {
                    "title": "开源社区动态",
                    "summary": "开源项目版本更新",
                    "link": "https://example.com/2",
                    "published_parsed": recent,
                },
                {
                    "title": "华为云发布新服务",
                    "summary": "云业务更新",
                    "link": "https://example.com/3",
                    "published_parsed": recent,
                },
                {
                    "title": "供应链关注华为新机",
                    "summary": "市场继续讨论新品",
                    "link": "https://example.com/4",
                    "published_parsed": recent,
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

    def test_fetch_items_excludes_entries_older_than_max_age_days(self):
        now = time.time()
        parsed = SimpleNamespace(
            feed={"title": "Tech Feed"},
            entries=[
                {
                    "title": "华为旧闻",
                    "summary": "这是较早之前的内容",
                    "link": "https://example.com/old",
                    "published_parsed": time.gmtime(now - 7 * 24 * 60 * 60),
                },
                {
                    "title": "华为最新动态",
                    "summary": "这是最近两小时的内容",
                    "link": "https://example.com/new",
                    "published_parsed": time.gmtime(now - 2 * 60 * 60),
                },
            ],
        )

        with (
            patch.object(send_news, "MATCH_KEYWORDS", ["华为"]),
            patch.object(send_news, "MAX_ITEM_AGE_DAYS", 1),
            patch.object(send_news.feedparser, "parse", return_value=parsed),
        ):
            items = send_news.fetch_items("https://example.com/rss")

        self.assertEqual([item["title"] for item in items], ["华为最新动态"])


class MainFlowTests(unittest.TestCase):
    def test_main_sorts_items_globally_by_publish_time_before_sending(self):
        newer = {
            "feed_title": "Feed B",
            "title": "华为更近的新闻",
            "summary": "B",
            "link": "https://example.com/b",
            "published_at": 200,
        }
        older = {
            "feed_title": "Feed A",
            "title": "华为较旧的新闻",
            "summary": "A",
            "link": "https://example.com/a",
            "published_at": 100,
        }

        with (
            patch.object(send_news, "load_feeds", return_value=["feed-a", "feed-b"]),
            patch.object(send_news, "fetch_items", side_effect=[[older], [newer]]),
            patch.object(send_news, "send_to_feishu") as mocked_send,
            patch.object(send_news, "MAX_TOTAL_ITEMS", 2),
        ):
            send_news.main()

        sent_text = mocked_send.call_args.args[0]
        self.assertLess(sent_text.index("华为更近的新闻"), sent_text.index("华为较旧的新闻"))

    def test_main_deduplicates_same_story_and_prefers_better_source(self):
        annual_cn = {
            "feed_title": "新闻动态",
            "title": "华为发布2025年年度报告：经营结果符合预期",
            "summary": "中文版本更适合当前机器人受众",
            "link": "https://www.huawei.com/cn/news/2026/3/annual-report-2025.html",
            "published_at": 300,
        }
        annual_en = {
            "feed_title": "Press Release",
            "title": "Huawei Releases 2025 Annual Report: Performance in Line with Forecast",
            "summary": "English variant of the same story",
            "link": "https://www.huawei.com/en/news/2026/3/annual-report-2025.html",
            "published_at": 290,
        }

        with (
            patch.object(send_news, "load_feeds", return_value=["feed-a", "feed-b"]),
            patch.object(send_news, "fetch_items", side_effect=[[annual_en], [annual_cn]]),
            patch.object(send_news, "send_to_feishu") as mocked_send,
            patch.object(send_news, "MAX_TOTAL_ITEMS", 5),
        ):
            send_news.main()

        sent_text = mocked_send.call_args.args[0]
        self.assertIn("华为发布2025年年度报告：经营结果符合预期", sent_text)
        self.assertNotIn("Huawei Releases 2025 Annual Report", sent_text)

    def test_main_fills_message_with_more_unique_items_after_dedup(self):
        duplicate_a = {
            "feed_title": "新闻动态",
            "title": "华为发布2025年年度报告：经营结果符合预期",
            "summary": "A",
            "link": "https://www.huawei.com/cn/news/2026/3/annual-report-2025.html",
            "published_at": 500,
        }
        duplicate_b = {
            "feed_title": "Press Release",
            "title": "Huawei Releases 2025 Annual Report: Performance in Line with Forecast",
            "summary": "B",
            "link": "https://www.huawei.com/en/news/2026/3/annual-report-2025.html",
            "published_at": 490,
        }
        item_2 = {
            "feed_title": "IT之家",
            "title": "华为 Mate 新机曝光",
            "summary": "2",
            "link": "https://example.com/2",
            "published_at": 480,
        }
        item_3 = {
            "feed_title": "36氪",
            "title": "华为云宣布新合作",
            "summary": "3",
            "link": "https://example.com/3",
            "published_at": 470,
        }
        item_4 = {
            "feed_title": "爱范儿",
            "title": "华为发布 AI 存储方案",
            "summary": "4",
            "link": "https://example.com/4",
            "published_at": 460,
        }

        with (
            patch.object(send_news, "load_feeds", return_value=["feed-a", "feed-b", "feed-c"]),
            patch.object(
                send_news,
                "fetch_items",
                side_effect=[
                    [duplicate_a, item_2],
                    [duplicate_b, item_3],
                    [item_4],
                ],
            ),
            patch.object(send_news, "send_to_feishu") as mocked_send,
            patch.object(send_news, "MAX_TOTAL_ITEMS", 4),
        ):
            send_news.main()

        sent_text = mocked_send.call_args.args[0]
        self.assertEqual(sent_text.count("\n\n"), 4)
        self.assertIn("华为发布 AI 存储方案", sent_text)
        self.assertNotIn("Huawei Releases 2025 Annual Report", sent_text)


if __name__ == "__main__":
    unittest.main()
