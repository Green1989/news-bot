---
name: verify
description: Run tests and syntax check to verify changes are correct
---

Run the full verification suite for this project:

1. `python -m py_compile send_news.py` — syntax check the main file
2. `python -m unittest discover -s tests -p 'test_*.py'` — run all tests

Report any failures. If all pass, confirm the codebase is clean.
