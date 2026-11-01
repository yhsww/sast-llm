"""CLI: load a SonarQube JSON report, run RAG + LLM, and save test cases."""
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

_REPORT_PATH = ROOT / "data" / "sast_reports" / "sample.json"

_PROVIDER_FOLDERS = {
    "openai": "GPT5.5",
    "gemini": "Gemini",
    "kimi": "Kimi",
    "claude": "Claude",
}


def _save_result(report_path: Path, output: dict) -> Path:
    provider = settings.llm_provider.strip().lower()

    folder = _PROVIDER_FOLDERS.get(
        provider,
        re.sub(r"[^a-zA-Z0-9._-]+", "-", provider),
    )

    output_dir = ROOT / "results" / folder
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{report_path.stem}_LLM.json"

    payload = json.dumps(
        output,
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    temporary_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )
    temporary_path.write_text(payload, encoding="utf-8")
    temporary_path.replace(output_path)

    return output_path


def main() -> None:
    report_path = _REPORT_PATH

    if not report_path.is_file():
        print(f"Report not found: {report_path}")
        sys.exit(1)

    report = SonarReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    print(f"Loaded {len(report.issues)} finding(s) from {report_path}.")

    user_context = input(
        "Optional focus/context (Enter to skip): "
    ).strip()

    print("\nQuerying knowledge base (CWE + WSTG)...")

    retrieved_per_finding = [
        query_knowledge(
            f"{issue.rule} {issue.message} {' '.join(issue.tags)}"
        )
        for issue in report.issues
    ]

    for index, docs in enumerate(retrieved_per_finding, start=1):
        print(
            f"  Finding {index}: "
            f"retrieved {[doc.id for doc in docs]}"
        )

    print("\nGenerating test cases...\n")

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

    print(json.dumps(
        output,
        indent=2,
        ensure_ascii=False,
    ))

    saved_path = _save_result(report_path, output)
    print(f"\n[SAVED] Result written to: {saved_path.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        provider = settings.llm_provider.strip().lower()
        folder = _PROVIDER_FOLDERS.get(
            provider,
            re.sub(r"[^a-zA-Z0-9._-]+", "-", provider),
        )
        error_dir = ROOT / "results" / folder
        error_dir.mkdir(parents=True, exist_ok=True)
        error_path = error_dir / f"{_REPORT_PATH.stem}_ERROR.txt"
        error_path.write_text(
            f"Report: {_REPORT_PATH.name}\n"
            f"Provider: {provider}\n"
            f"Error: {type(exc).__name__}: {exc}\n",
            encoding="utf-8",
        )
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"[ERROR FILE] {error_path.relative_to(ROOT)}", file=sys.stderr)
        raise SystemExit(1)
