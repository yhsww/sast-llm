"""CLI entry point for Branch 3: RAG + CWE/WSTG + source-code context.

Examples:
    python query.py --help
    python query.py --provider GPT --only GT01.json
    python query.py --provider Gemini --allreports
    python query.py --provider all --allreports --execute
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from scripts.run_gt_experiment import main


if __name__ == "__main__":
    raise SystemExit(main())
