
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.schemas import SonarReport
from backend.chroma_service import query_knowledge
from backend.openai_service import generate_test_cases


def main():
    parser = argparse.ArgumentParser(
        description="Run GT01-GT08 using CWE + WSTG RAG."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Authorize real API calls to the configured provider.",
    )
    args = parser.parse_args()

    if settings.llm_provider.strip().lower() != "gemini":
        raise SystemExit(
            "Execution cancelled: LLM_PROVIDER is not set to gemini."
        )

    input_dir = ROOT / "data" / "sast_reports"
    output_dir = (
        ROOT / "results" / "branch-2-rag-cwe-wstg" / "Gemini"
    )

    files = [
        input_dir / f"GT{i:02d}.json"
        for i in range(1, 9)
    ]

    missing = [
        str(path)
        for path in files
        if not path.is_file()
    ]

    if missing:
        raise SystemExit(
            "Missing reports:\n" + "\n".join(missing)
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Configured provider: Gemini ({settings.gemini_model})")
    print(f"Output directory: {output_dir.relative_to(ROOT)}")
    print(
        f"Mode: {'LIVE EXECUTION' if args.execute else 'LOCAL SIMULATION'}"
    )

    for report_path in files:
        name = report_path.stem
        output_path = output_dir / f"{name}_LLM.json"
        error_path = output_dir / f"{name}_ERROR.txt"

        # Preserve results that have already been generated.
        if output_path.exists():
            print(f"{name}: skipped; result already exists.")
            continue

        # Allow previously failed GTs to be retried.
        if error_path.exists():
            if not args.execute:
                print(
                    f"{name}: previous error exists; "
                    "eligible for retry during live execution."
                )
                continue

            error_path.unlink()
            print(
                f"{name}: previous error record removed "
                "to allow a retry."
            )

        try:
            data = json.loads(
                report_path.read_text(encoding="utf-8")
            )
            report = SonarReport.model_validate(data)

            retrieved = [
                query_knowledge(
                    f"{issue.rule} {issue.message} "
                    f"{' '.join(issue.tags)}"
                )
                for issue in report.issues
            ]

            retrieved_ids = [
                [doc.id for doc in docs]
                for docs in retrieved
            ]

            print(
                f"{name}: {len(report.issues)} finding(s); "
                f"RAG context={retrieved_ids}"
            )

            # Local simulation does not call the generative model.
            if not args.execute:
                continue

            generated = generate_test_cases(
                report.issues,
                "",
                retrieved,
            )

            if len(generated.test_cases) != len(report.issues):
                raise ValueError(
                    f"Expected {len(report.issues)} test case(s); "
                    f"received {len(generated.test_cases)}."
                )

            payload = json.dumps(
                generated.model_dump(),
                ensure_ascii=False,
                indent=2,
            )

            # Exclusive mode prevents overwriting existing results.
            with output_path.open("x", encoding="utf-8") as file:
                file.write(payload + "\n")

            print(
                f"{name}: result saved to {output_path.name}"
            )

        except Exception as exc:
            if not args.execute:
                raise

            message = f"{type(exc).__name__}: {exc}\n"

            try:
                with error_path.open("x", encoding="utf-8") as file:
                    file.write(message)

                print(
                    f"{name}: error recorded in {error_path.name}"
                )

            except FileExistsError:
                print(
                    f"{name}: failed; error record already exists."
                )

    if not args.execute:
        print(
            "\nSimulation completed. "
            "No generation API calls were made."
        )
        print(
            "To start live generation, run the script with --execute."
        )


if __name__ == "__main__":
    main()
