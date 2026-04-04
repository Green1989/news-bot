# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Test: `python -m unittest discover -s tests -p 'test_*.py'`
- Syntax check: `python -m py_compile send_news.py`

## Conventions

- Commit messages in Chinese, plain descriptions without conventional-commits prefixes (e.g., "优化新闻时效性", "增加回国外的源")
- feeds.txt uses `# comment` lines and blank lines to separate sections — preserve this format when editing

## Required Environment

- `FEISHU_WEBHOOK` — mandatory, code crashes at import if missing (`os.environ["FEISHU_WEBHOOK"]`)
- For local testing, set it to any URL: `FEISHU_WEBHOOK=https://example.com/webhook`

## Architecture

- Single-file design: all logic in `send_news.py`, no module split
- Flow: load_feeds → fetch_items (per feed) → deduplicate_items → build_message → send_to_feishu
- Dedup uses URL slug + normalized title; source_priority prefers Chinese sources over English
- Tests mock feedparser/requests/bs4 at module level before importing send_news
