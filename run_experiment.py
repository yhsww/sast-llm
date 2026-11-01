"""Compatibility entry point for the Branch 1 direct-LLM experiment.

The implementation lives in query.py so both commands use the same input
discovery, provider selection, output naming, and error handling.
"""
from query import main


if __name__ == "__main__":
    raise SystemExit(main())
