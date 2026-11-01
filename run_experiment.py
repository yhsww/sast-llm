"""Compatibility entry point for the main-branch query runner.

The main branch uses query.py to read data/sast_reports/sample.json, ask which
LLM provider to use, and save the generated JSON report under results/.
"""

from query import main


if __name__ == "__main__":
    raise SystemExit(main())
