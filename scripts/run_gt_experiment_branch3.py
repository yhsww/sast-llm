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


SOURCE_ROOT = (ROOT.parent / "juice-shop-validation").resolve()
CONTEXT_LINES = 10


def extract_code_context(issues):
    sections = []

    for index, issue in enumerate(issues, start=1):
        component = issue.component or ""
        relative_path = component.split(":", 1)[-1].lstrip("/")
        source_path = (SOURCE_ROOT / relative_path).resolve()

        try:
            source_path.relative_to(SOURCE_ROOT)
        except ValueError:
            sections.append(
                f"Finding {index}: rejected unsafe source path "
                f"{relative_path!r}."
            )
            continue

        if not source_path.is_file():
            sections.append(
                f"Finding {index}: source file not found: {relative_path}"
            )
            continue

        try:
            lines = source_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError as exc:
            sections.append(
                f"Finding {index}: could not read {relative_path}: {exc}"
            )
            continue

        line_number = issue.line
        if line_number is None and issue.textRange is not None:
            line_number = issue.textRange.startLine

        if line_number is None:
            sections.append(
                f"Finding {index}: source file {relative_path}; "
                "the finding has no line number."
            )
            continue

        start = max(1, line_number - CONTEXT_LINES)
        end = min(len(lines), line_number + CONTEXT_LINES)

        snippet = "\n".join(
            f"{number}: {lines[number - 1]}"
            for number in range(start, end + 1)
        )

        sections.append(
            f"Finding {index}\n"
            f"File: {relative_path}\n"
            f"Sonar finding line: {line_number}\n"
            f"Source lines {start}-{end}:\n{snippet}"
        )

    return "\n\n".join(sections)


def main():
    parser = argparse.ArgumentParser(
        description="Run GT01-GT08 using CWE + WSTG RAG and local source context."
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

    if not SOURCE_ROOT.is_dir():
        raise SystemExit(f"Source repository not found: {SOURCE_ROOT}")

    input_dir = ROOT / "data" / "sast_reports"
    output_dir = ROOT / "results" / "branch-3-rag-code-context" / "Gemini"

    files = [input_dir / f"GT{i:02d}.json" for i in range(1, 9)]
    missing = [str(path) for path in files if not path.is_file()]

    if missing:
        raise SystemExit("Missing reports:\n" + "\n".join(missing))

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Configured provider: Gemini ({settings.gemini_model})")
    print(f"Source repository: {SOURCE_ROOT}")
    print(f"Output directory: {output_dir.relative_to(ROOT)}")
    print(
        f"Mode: {'LIVE EXECUTION' if args.execute else 'LOCAL SIMULATION'}"
    )

    for report_path in files:
        name = report_path.stem
        output_path = output_dir / f"{name}_LLM.json"
        error_path = output_dir / f"{name}_ERROR.txt"

        if output_path.exists():
            print(f"{name}: skipped; result already exists.")
            continue

        if error_path.exists():
            if not args.execute:
                print(
                    f"{name}: previous error exists; "
                    "eligible for retry during live execution."
                )
                continue

            error_path.unlink()
            print(f"{name}: previous error record removed for retry.")

        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            report = SonarReport.model_validate(data)

            retrieved = [
                query_knowledge(
                    f"{issue.rule} {issue.message} {' '.join(issue.tags)}"
                )
                for issue in report.issues
            ]

            code_context = extract_code_context(report.issues)
            retrieved_ids = [[doc.id for doc in docs] for docs in retrieved]

            print(
                f"{name}: {len(report.issues)} finding(s); "
                f"RAG context={retrieved_ids}"
            )
            print(
                f"{name}: source context prepared "
                f"({len(code_context)} characters)."
            )

            if not args.execute:
                if code_context:
                    print(code_context)
                continue

            generated = generate_test_cases(
                report.issues,
                code_context,
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

            with output_path.open("x", encoding="utf-8") as file:
                file.write(payload + "\n")

            print(f"{name}: result saved to {output_path.name}")

        except Exception as exc:
            if not args.execute:
                raise

            message = f"{type(exc).__name__}: {exc}\n"
            try:
                with error_path.open("x", encoding="utf-8") as file:
                    file.write(message)
                print(f"{name}: error recorded in {error_path.name}")
            except FileExistsError:
                print(f"{name}: failed; error record already exists.")

    if not args.execute:
        print("\nSimulation completed. No generation API calls were made.")
        print("Review the source context before authorizing live generation.")
        print("For live generation, run this script with --execute.")


if __name__ == "__main__":
    main()
