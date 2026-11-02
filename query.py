"""CLI for the CWE + WSTG RAG experiment.

Examples:
    python query.py --sample.json --provider kimi
    python query.py --GT01.json --provider openai
    python query.py --report GT02.json --provider gemini
    python query.py --allreports --provider claude
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.schemas import SonarReport, SecurityTestCase
from backend.chroma_service import query_knowledge
from backend.openai_service import generate_test_cases

REPORTS_DIR = ROOT / "data" / "sast_reports"
PROVIDERS = ("openai", "gemini", "kimi", "claude")
PROVIDER_FOLDERS = {
    "openai": "GPT5.5",
    "gpt": "GPT5.5",
    "gpt5.5": "GPT5.5",
    "gemini": "Gemini",
    "kimi": "Kimi",
    "claude": "Claude",
}


def _provider_folder(provider: str) -> str:
    normalized = provider.strip().lower()
    return PROVIDER_FOLDERS.get(
        normalized,
        re.sub(r"[^a-zA-Z0-9._-]+", "-", normalized),
    )


def _save_result(report_path: Path, output: dict, provider: str) -> Path:
    output_dir = ROOT / "results" / _provider_folder(provider)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{report_path.stem}_LLM.json"
    payload = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(payload, encoding="utf-8")
    temporary_path.replace(output_path)
    return output_path


def _save_error(report_path: Path, provider: str, exc: Exception) -> Path:
    error_dir = ROOT / "results" / _provider_folder(provider)
    error_dir.mkdir(parents=True, exist_ok=True)
    error_path = error_dir / f"{report_path.stem}_ERROR.txt"
    error_path.write_text(
        f"Report: {report_path.name}\n"
        f"Provider: {provider}\n"
        f"Error: {type(exc).__name__}: {exc}\n",
        encoding="utf-8",
    )
    return error_path


def _available_reports() -> list[Path]:
    if not REPORTS_DIR.is_dir():
        return []
    return sorted(
        (path for path in REPORTS_DIR.glob("*.json") if path.is_file()),
        key=lambda path: path.name.lower(),
    )


def _parse_args() -> argparse.Namespace:
    available_names = [path.name for path in _available_reports()]
    parser = argparse.ArgumentParser(
        description="Run CWE + WSTG RAG against one or all SonarQube JSON reports."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--allreports",
        action="store_true",
        help="process every *.json report in data/sast_reports",
    )
    selection.add_argument(
        "--report",
        choices=available_names,
        metavar="ARQUIVO.json",
        help="select a report by filename (e.g. --report GT01.json)",
    )
    # Preserve the requested shortcut syntax: --sample.json, --GT01.json, etc.
    for name in available_names:
        selection.add_argument(
            f"--{name}",
            dest="report_flag",
            action="store_const",
            const=name,
            help=f"select data/sast_reports/{name}",
        )
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=settings.llm_provider.strip().lower(),
        help="LLM provider (default: value from .env)",
    )
    return parser.parse_args()


def _run_report(report_path: Path, user_context: str, provider: str) -> bool:
    try:
        if not report_path.is_file():
            raise FileNotFoundError(f"Report not found: {report_path}")

        report = SonarReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        print(f"\nLoaded {len(report.issues)} finding(s) from {report_path.name}.")

        print("Querying knowledge base (CWE + WSTG)...")
        retrieved_per_finding = [
            query_knowledge(
                f"{issue.rule} {issue.message} {' '.join(issue.tags)}"
            )
            for issue in report.issues
        ]

        for index, docs in enumerate(retrieved_per_finding, start=1):
            print(f"  Finding {index}: retrieved {[doc.id for doc in docs]}")

        print(f"Generating test cases with provider '{provider}'...")
        generated = generate_test_cases(
            report.issues,
            user_context,
            retrieved_per_finding,
        )
        test_cases = [
            SecurityTestCase(**case.model_dump())
            for case in generated.test_cases
        ]
        output = {
            "test_cases": [
                case.model_dump(mode="json")
                for case in test_cases
            ]
        }

        saved_path = _save_result(report_path, output, provider)
        print(f"[SAVED] Result written to: {saved_path.resolve()}")
        return True
    except Exception as exc:
        error_path = _save_error(report_path, provider, exc)
        print(
            f"[ERROR] {report_path.name}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(f"[ERROR FILE] {error_path.relative_to(ROOT)}", file=sys.stderr)
        return False


def main() -> None:
    args = _parse_args()
    provider = args.provider.strip().lower()
    # Provider selection from CLI takes precedence over .env.
    settings.llm_provider = provider

    if args.allreports:
        report_paths = _available_reports()
        if not report_paths:
            print(f"No JSON reports found in {REPORTS_DIR}", file=sys.stderr)
            raise SystemExit(1)
    else:
        selected_name = args.report or getattr(args, "report_flag", None)
        if not selected_name:
            print("Select --allreports, --report FILE.json, or a --FILE.json shortcut.")
            raise SystemExit(2)
        report_paths = [REPORTS_DIR / selected_name]

    user_context = input(
        "Optional focus/context (Enter to skip): "
    ).strip()

    successes = 0
    for report_path in report_paths:
        successes += int(_run_report(report_path, user_context, provider))

    print(
        f"\nFinished: {successes}/{len(report_paths)} report(s) succeeded. "
        f"Output folder: results/{_provider_folder(provider)}/"
    )
    if successes != len(report_paths):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
