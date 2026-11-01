import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.schemas import SonarReport
from backend.chroma_service import query_knowledge
from backend.openai_service import generate_test_cases


PROVIDERS = [
    {"key": "openai", "name": "GPT", "model_attr": "openai_chat_model", "api_key_attr": "openai_api_key"},
    {"key": "gemini", "name": "Gemini", "model_attr": "gemini_model", "api_key_attr": "google_api_key"},
    {"key": "kimi", "name": "Kimi", "model_attr": "kimi_model", "api_key_attr": "kimi_api_key"},
    {"key": "claude", "name": "Claude", "model_attr": "claude_model", "api_key_attr": "anthropic_api_key"},
]


def build_retrieval_query(issue) -> str:
    """Build a compact RAG query; avoid code, HTML, and long rule descriptions."""
    rule = getattr(issue, "rule", "")
    if isinstance(rule, dict):
        rule_key = rule.get("key", "")
        rule_name = rule.get("name", "")
        rule_tags = rule.get("tags", [])
    else:
        rule_key, rule_name, rule_tags = str(rule or ""), "", []

    tags = getattr(issue, "tags", []) or []
    if isinstance(tags, str):
        tags = [tags]
    if isinstance(rule_tags, str):
        rule_tags = [rule_tags]

    parts = [
        rule_key, rule_name, str(getattr(issue, "message", "") or ""),
        *[str(tag) for tag in tags[:8] if tag],
        *[str(tag) for tag in rule_tags[:8] if tag],
        str(getattr(issue, "type", "") or ""),
        str(getattr(issue, "severity", "") or ""),
    ]
    cleaned, seen = [], set()
    for part in parts:
        part = re.sub(r"<[^>]+>", " ", part)
        part = re.sub(r"\s+", " ", part).strip()
        if part and part.casefold() not in seen:
            seen.add(part.casefold())
            cleaned.append(part)
    return " ".join(cleaned)


def concise_error(exc):
    message = str(exc).lower()
    if any(term in message for term in ("exceeded_current_quota_error", "insufficient balance", "quota exceeded", "resource_exhausted")):
        return "API quota or balance exceeded."
    if "rate_limit" in message or "rate limit" in message:
        return "API rate limit reached."
    if any(term in message for term in ("authentication", "invalid api key", "unauthorized", "401")):
        return "API authentication failed."
    if "timeout" in message or "timed out" in message:
        return "Request timed out."
    if any(term in message for term in ("503", "service unavailable", "overloaded")):
        return "Provider temporarily unavailable."
    if isinstance(exc, FileNotFoundError):
        return "Required file not found."
    if isinstance(exc, json.JSONDecodeError):
        return "Invalid JSON."
    if isinstance(exc, ValueError):
        return "Invalid data or unexpected model output."
    return f"{type(exc).__name__}: operation failed."


def save_error(path, exc):
    path.write_text(f"Error type: {type(exc).__name__}\nError message: {exc}\n", encoding="utf-8")


def run_provider(provider, reports, execute):
    key, name = provider["key"], provider["name"]
    model = getattr(settings, provider["model_attr"], None)
    api_key = getattr(settings, provider["api_key_attr"], None)
    output_dir = ROOT / "results" / name

    print(f"\n{'=' * 50}")
    print(f"LLM: {name}")
    print(f"Model: {model or 'not configured'}")
    print(f"Output: results/{name}")
    print(f"Mode: {'LIVE EXECUTION' if execute else 'SIMULATION'}")
    print("=" * 50)

    if not model:
        print(f"[SKIP] {name}: model is not configured.")
        return {"ok": 0, "error": 0, "skip": len(reports)}
    if execute and not api_key:
        print(f"[SKIP] {name}: API key is not configured.")
        return {"ok": 0, "error": 0, "skip": len(reports)}
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        print(f"[ERROR] {name}: cannot create output directory.")
        return {"ok": 0, "error": len(reports), "skip": 0}

    totals = {"ok": 0, "error": 0, "skip": 0}
    settings.llm_provider = key

    for report_path in reports:
        gt = report_path.stem
        output_path = output_dir / f"{gt}_LLM.json"
        error_path = output_dir / f"{gt}_ERROR.txt"
        if output_path.exists():
            print(f"[SKIP] {gt}: result already exists.")
            totals["skip"] += 1
            continue

        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            report = SonarReport.model_validate(data)
            retrieval_queries = [build_retrieval_query(issue) for issue in report.issues]
            retrieved = [query_knowledge(query) for query in retrieval_queries]
            retrieved_ids = [[doc.id for doc in docs] for docs in retrieved]
            print(
                f"[INFO] {gt}: {len(report.issues)} finding(s); "
                f"RAG queries={retrieval_queries}; documents={retrieved_ids}"
            )

            if not execute:
                totals["ok"] += 1
                continue

            generated = generate_test_cases(report.issues, "", retrieved)
            if len(generated.test_cases) != len(report.issues):
                raise ValueError(
                    f"Expected {len(report.issues)} test cases; received {len(generated.test_cases)}."
                )
            payload = json.dumps(generated.model_dump(), ensure_ascii=False, indent=2)
            with output_path.open("x", encoding="utf-8") as file:
                file.write(payload + "\n")
            if error_path.exists():
                error_path.unlink()
            print(f"[OK] {gt}: result saved.")
            totals["ok"] += 1
        except Exception as exc:
            print(f"[ERROR] {gt}: {concise_error(exc)}")
            totals["error"] += 1
            if execute:
                try:
                    save_error(error_path, exc)
                except OSError:
                    print(f"[WARN] {gt}: could not save error log.")

    print(f"[SUMMARY] {name}: OK={totals['ok']}, ERROR={totals['error']}, SKIPPED={totals['skip']}")
    return totals


def main():
    parser = argparse.ArgumentParser(description="Run GT01-GT08 across all configured LLM providers.")
    parser.add_argument("--execute", action="store_true", help="Enable real LLM API calls.")
    args = parser.parse_args()

    input_dir = ROOT / "data" / "sast_reports"
    reports = [input_dir / f"GT{i:02d}.json" for i in range(1, 9)]
    missing = [path.name for path in reports if not path.is_file()]
    if missing:
        raise SystemExit(f"[ERROR] Missing input reports: {', '.join(missing)}.")

    print("SAST LLM Experiment")
    print("Providers: GPT, Gemini, Kimi, Claude")
    print(f"Reports: {len(reports)}")
    total = {"ok": 0, "error": 0, "skip": 0}
    for provider in PROVIDERS:
        result = run_provider(provider, reports, args.execute)
        for key in total:
            total[key] += result[key]

    print("\n" + "=" * 50)
    print("FINAL SUMMARY")
    print(f"[OK] Succeeded: {total['ok']}")
    print(f"[ERROR] Failed: {total['error']}")
    print(f"[SKIP] Skipped: {total['skip']}")
    if not args.execute:
        print("\nSimulation only. No generation API calls were made.")
        print("Run with --execute for actual generation.")


if __name__ == "__main__":
    main()
