# Huawei News Dedup Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Increase the number of Feishu news items to 8-12 while removing duplicate stories across sources.

**Architecture:** Keep the existing feed fetch, keyword filtering, and recency filtering. Add a post-fetch normalization and deduplication pass that scores candidates, chooses the best representative per story cluster, then sorts by publish time before building the final message.

**Tech Stack:** Python 3.11, feedparser, unittest

---

### Task 1: Add failing tests for deduplication and richer output

**Files:**
- Modify: `tests/test_send_news.py`
- Test: `tests/test_send_news.py`

**Step 1: Write the failing test**

Add tests that prove:
- duplicate Chinese/English variants of the same annual report collapse into one item
- the final message can include more unique items when `MAX_TOTAL_ITEMS` is raised

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p 'test_*.py'`
Expected: FAIL on the new deduplication assertions

**Step 3: Write minimal implementation**

Add normalization, deduplication, and source-priority selection in `send_news.py`.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS

### Task 2: Expand candidate pool and tune workflow defaults

**Files:**
- Modify: `send_news.py`
- Modify: `.github/workflows/daily-news.yml`

**Step 1: Write the failing test**

Add a test that verifies more unique items survive after deduplication when multiple feeds return candidates.

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p 'test_*.py'`
Expected: FAIL because current pipeline truncates too early or keeps duplicates

**Step 3: Write minimal implementation**

Raise candidate limits in the workflow and perform deduplication before final truncation.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS

### Task 3: Verify and document behavior

**Files:**
- Modify: `README.md`

**Step 1: Update docs**

Document how uniqueness and count are now determined.

**Step 2: Run verification**

Run:
- `python -m unittest discover -s tests -p 'test_*.py'`
- `python -m py_compile send_news.py`

Expected: both commands succeed
