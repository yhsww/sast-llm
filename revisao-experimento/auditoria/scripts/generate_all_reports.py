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

INPUT_DIR = ROOT / "data" / "sast_reports"
SOURCE_ROOT = (ROOT.parent / "juice-shop-validation").resolve()
CONTEXT_LINES = 10

BRANCHES = {
    "branch1": ("branch-1-direct-llm", "direct"),
    "branch2": ("branch-2-rag-cwe-wstg", "rag"),
    "branch3": ("branch-3-rag-code-context", "rag_code"),
}
PROVIDERS = {
    "gemini": ("Gemini", settings.gemini_model, settings.google_api_key),
    "kimi": ("Kimi", settings.kimi_model, settings.kimi_api_key),
    "claude": ("Claude", settings.claude_model, settings.anthropic_api_key),
}


def extract_code_context(issues):
    sections = []
    for index, issue in enumerate(issues, start=1):
        component = issue.component or ""
        relative_path = component.split(":", 1)[-1].lstrip("/")
        source_path = (SOURCE_ROOT / relative_path).resolve()
        try:
            source_path.relative_to(SOURCE_ROOT)
        except ValueError:
            sections.append(f"Finding {index}: rejected unsafe source path {relative_path!r}.")
            continue
        if not source_path.is_file():
            sections.append(f"Finding {index}: source file not found: {relative_path}")
            continue
        try:
            lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            sections.append(f"Finding {index}: could not read {relative_path}: {exc}")
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
        snippet = "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))
        sections.append(
            f"Finding {index}\nFile: {relative_path}\nSonar finding line: {line_number}\n"
            f"Source lines {start}-{end}:\n{snippet}"
        )
    return "\n\n".join(sections)


def load_report(report_path):
    data = json.loads(report_path.read_text(encoding="utf-8"))
    return SonarReport.model_validate(data)


def get_retrieved(report):
    return [
        query_knowledge(f"{issue.rule} {issue.message} {' '.join(issue.tags)}")
        for issue in report.issues
    ]


def run_one(branch_key, provider_key, execute):
    branch_dir, mode = BRANCHES[branch_key]
    provider_dir, model, api_key = PROVIDERS[provider_key]
    output_dir = ROOT / "results" / branch_dir / provider_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[{branch_key} | {provider_dir}] model={model}")
    print(f"Output: {output_dir.relative_to(ROOT)}")
    if not api_key:
        print(f"SKIP: API key for {provider_dir} is not configured.")
        return
    for index in range(1, 9):
        report_path = INPUT_DIR / f"GT{index:02d}.json"
        name = report_path.stem
        output_path = output_dir / f"{name}_LLM.json"
        error_path = output_dir / f"{name}_ERROR.txt"
        if output_path.exists():
            print(f"{name}: skipped; JSON already exists.")
            continue
        if error_path.exists():
            print(f"{name}: skipped; existing error file preserved.")
            continue
        if not report_path.is_file():
            print(f"{name}: input report missing: {report_path}")
            continue
        try:
            report = load_report(report_path)
            if mode == "direct":
                retrieved = [[] for _ in report.issues]
                user_context = ""
            else:
                retrieved = get_retrieved(report)
                user_context = ""
            if mode == "rag_code":
                if not SOURCE_ROOT.is_dir():
                    raise FileNotFoundError(f"Source repository not found: {SOURCE_ROOT}")
                user_context = extract_code_context(report.issues)
            print(
                f"{name}: {len(report.issues)} finding(s); mode={mode}; "
                f"RAG={'no' if mode == 'direct' else 'yes'}"
            )
            if not execute:
                print(f"{name}: simulation only; no generation API call.")
                continue
            generated = generate_test_cases(report.issues, user_context, retrieved)
            if len(generated.test_cases) != len(report.issues):
                raise ValueError(
                    f"Expected {len(report.issues)} test case(s); "
                    f"received {len(generated.test_cases)}."
                )
            payload = json.dumps(generated.model_dump(), ensure_ascii=False, indent=2)
            # Exclusive creation guarantees that existing output is never overwritten.
            with output_path.open("x", encoding="utf-8") as file:
                file.write(payload + "\n")
            print(f"{name}: saved {output_path.name}")
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}\n"
            try:
                with error_path.open("x", encoding="utf-8") as file:
                    file.write(message)
                print(f"{name}: error recorded in {error_path.name}")
            except FileExistsError:
                print(f"{name}: error occurred; existing error file preserved.")
            if not execute:
                raise


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate GT01-GT08 for direct LLM, CWE/WSTG RAG, "
            "and RAG plus source-code context."
        )
    )
    parser.add_argument(
        "--provider",
        choices=("gemini", "kimi", "claude"),
        default=settings.llm_provider.strip().lower(),
        help="Provider to use. Defaults to LLM_PROVIDER from .env.",
    )
    parser.add_argument(
        "--branch",
        choices=("all", "branch1", "branch2", "branch3"),
        default="all",
        help="Branch to run; defaults to all three.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Authorize real generation API calls. Without it, only simulates.",
    )
    args = parser.parse_args()
    provider_key = args.provider
    settings.llm_provider = provider_key
    print(f"Provider: {provider_key} ({PROVIDERS[provider_key][1]})")
    print(f"Mode: {'LIVE API EXECUTION' if args.execute else 'SIMULATION (no generation API calls)'}")
    branches = list(BRANCHES) if args.branch == "all" else [args.branch]
    for branch_key in branches:
        run_one(branch_key, provider_key, args.execute)
    if not args.execute:
        print("\nSimulation complete. No generation API calls were made.")
        print("Use --execute only when ready to generate real reports.")


if __name__ == "__main__":
    main()
