"""Entry point for Branch 3: RAG with CWE/WSTG and code context.

Use --execute to call the selected LLM. Without it, the script performs a dry run.
Code snippets are loaded from data/code_snippets/<report>.json or can be extracted
from source files with --source-root.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from scripts.run_gt_experiment import main


if __name__ == "__main__":
    main()
