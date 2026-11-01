"""Branch 3 runner: RAG + source-code context.

Input reports:
    data/sast_reports/GT*.json

Optional snippets:
    data/code_snippets/GT01.json

Outputs:
    results/GPT5.5/GT01_LLM.json
    results/Gemini/GT01_LLM.json
    results/Kimi/GT01_LLM.json
    results/Claude/GT01_LLM.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from backend.config import settings
from backend.schemas import SecurityTestReport, SonarReport
from backend.chroma_service import query_knowledge
from backend.openai_service import _SYSTEM_PROMPT, _build_finding_block


# Each provider has its own output folder.
PROVIDERS = {
    "GPT": {
        "api_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_CHAT_MODEL",
        "model": "gpt-5.5",
        "folder": "GPT5.5",
    },
    "Gemini": {
        "api_env": "GOOGLE_API_KEY",
        "model_env": "GEMINI_MODEL",
        "model": "gemini-3.8-flash",
        "folder": "Gemini",
    },
    "Kimi": {
        "api_env": "KIMI_API_KEY",
        "model_env": "KIMI_MODEL",
        "model": "moonshot-v1-8k",
        "folder": "Kimi",
    },
    "Claude": {
        "api_env": "ANTHROPIC_API_KEY",
        "model_env": "CLAUDE_MODEL",
        "model": "claude-sonnet-4-5",
        "folder": "Claude",
    },
}


def model_for(name: str) -> str:
    cfg = PROVIDERS[name]

    # Use the configured OpenAI model when available.
    configured = (
        getattr(settings, "openai_chat_model", None)
        if name == "GPT"
        else None
    )

    return (
        os.getenv(cfg["model_env"])
        or configured
        or cfg["model"]
    ).strip()


def output_folder_for(name: str) -> str:
    """Return the folder assigned to a provider."""
    return PROVIDERS[name]["folder"]


def api_key_for(name: str) -> str:
    if name == "GPT":
        return os.getenv(
            "OPENAI_API_KEY",
            getattr(settings, "openai_api_key", "")
        ).strip()

    return os.getenv(PROVIDERS[name]["api_env"], "").strip()


def load_snippets(
    report_path: Path,
    raw: dict[str, Any],
    report: SonarReport,
    snippets_dir: Path,
) -> list[str | None]:
    """Load code snippets from the report or an optional separate JSON file."""
    value: Any = raw.get("code_snippets")
    snippet_path = snippets_dir / f"{report_path.stem}.json"

    if value is None and snippet_path.is_file():
        try:
            value = json.loads(snippet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read {snippet_path}: {exc}") from exc

    if isinstance(value, dict) and "code_snippets" in value:
        value = value["code_snippets"]

    if isinstance(value, list):
        values = [
            v if isinstance(v, str) and v.strip() else None
            for v in value
        ]
        return (values + [None] * len(report.issues))[:len(report.issues)]

    if isinstance(value, dict):
        snippets = []

        for index, issue in enumerate(report.issues, start=1):
            keys = [
                str(index),
                issue.key or "",
                issue.component or "",
                issue.rule,
            ]

            item = next(
                (value[k] for k in keys if k and k in value),
                None
            )

            snippets.append(
                item if isinstance(item, str) and item.strip() else None
            )

        return snippets

    if value is not None:
        raise ValueError(
            f"Unsupported snippet format in {snippet_path}; use a list or object."
        )

    return [None] * len(report.issues)


def extract_source_snippets(
    report: SonarReport,
    source_root: Path,
    radius: int = 15,
) -> list[str | None]:
    """Extract nearby source lines using Sonar component paths and issue line numbers."""
    snippets: list[str | None] = []
    root = source_root.resolve()

    for issue in report.issues:
        component = issue.component or ""
        relative = component.split(":", 1)[1] if ":" in component else component
        relative = relative.replace("\\", "/").lstrip("/")
        candidate = (root / relative).resolve()

        try:
            candidate.relative_to(root)
        except ValueError:
            snippets.append(None)
            continue

        line_number = issue.line or (
            issue.textRange.startLine if issue.textRange else None
        )

        if not candidate.is_file() or not line_number:
            snippets.append(None)
            continue

        try:
            lines = candidate.read_text(
                encoding="utf-8",
                errors="replace"
            ).splitlines()
        except OSError:
            snippets.append(None)
            continue

        if line_number < 1 or line_number > len(lines):
            snippets.append(None)
            continue

        start = max(1, line_number - radius)
        end = min(len(lines), line_number + radius)

        snippet = "\n".join(
            f"{n:>5}: {lines[n - 1]}"
            for n in range(start, end + 1)
        )

        snippets.append(
            f"Source: {candidate.name} (lines {start}-{end})\n{snippet}"
        )

    return snippets


def parse_response(text: str) -> SecurityTestReport:
    """Parse a provider response as a SecurityTestReport."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")

        if start >= 0 and end > start:
            text = text[start:end + 1]

    return SecurityTestReport.model_validate(json.loads(text))


def build_user_content(issues, retrieved, snippets: list[str | None]) -> str:
    """Monta o prompt com os achados, o código vulnerável e o contexto RAG."""
    snippets = list(snippets) + [None] * max(0, len(issues) - len(snippets))
    blocks = []

    for index, (issue, docs) in enumerate(
        zip(issues, retrieved), start=1
    ):
        lines = [
            f"--- Finding {index} ---",
            f"Rule: {getattr(issue, 'rule', 'N/A')}",
            f"Severity: {getattr(issue, 'severity', 'N/A')}",
            f"Message: {getattr(issue, 'message', 'N/A')}",
            f"Component: {getattr(issue, 'component', None) or 'N/A'}",
            f"Line: {getattr(issue, 'line', None) or 'N/A'}",
        ]

        snippet = snippets[index - 1]
        if snippet and snippet.strip():
            lines.extend([
                "",
                "[Vulnerable Source Code]",
                "```",
                snippet.strip(),
                "```",
            ])

        for doc in docs:
            lines.extend([
                "",
                f"[{getattr(doc, 'source', 'Reference')} "
                f"Reference: {getattr(doc, 'id', 'N/A')}]",
                getattr(doc, 'title', '') or '',
                (getattr(doc, 'content', '') or '')[:1500],
            ])

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def generate(provider: str, user_content: str) -> SecurityTestReport:
    """Call the selected provider and parse its generated test cases."""
    key = api_key_for(provider)
    model = model_for(provider)

    if not key:
        raise RuntimeError(
            f"Missing {PROVIDERS[provider]['api_env']} for {provider} in .env."
        )

    if provider in ("GPT", "Kimi"):
        from openai import OpenAI

        kwargs = {"api_key": key}

        if provider == "Kimi":
            kwargs["base_url"] = os.getenv(
                "KIMI_BASE_URL",
                "https://api.moonshot.ai/v1"
            )

        client = OpenAI(**kwargs)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content

        if not text:
            raise ValueError(f"{provider} returned an empty response.")

        result = parse_response(text)

    elif provider == "Gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        response = client.models.generate_content(
            model=model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=SecurityTestReport,
            ),
        )

        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        result = parse_response(response.text)

    else:
        from anthropic import Anthropic

        client = Anthropic(api_key=key)

        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        chunks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]

        if not chunks:
            raise ValueError("Claude returned no text content.")

        result = parse_response("\n".join(chunks))

    return result


def discover_reports(
    input_dir: Path,
    requested: str | None,
) -> list[Path]:
    """Find the requested report or all GT*.json reports."""
    if requested:
        path = input_dir / (
            requested if requested.endswith(".json") else f"{requested}.json"
        )

        if not path.is_file():
            raise SystemExit(f"[ERROR] Report not found: {path}")

        return [path]

    reports = list(input_dir.glob("GT*.json"))

    reports.sort(
        key=lambda p: (
            int(re.search(r"GT(\d+)", p.stem).group(1))
            if re.search(r"GT(\d+)", p.stem)
            else 10**9
        )
    )

    if not reports:
        raise SystemExit(f"[ERROR] No GT*.json files found in {input_dir}")

    return reports


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Branch 3 experiment: RAG + code context"
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Call the selected LLM APIs to generate results.",
    )
    parser.add_argument(
        "--provider",
        choices=[*PROVIDERS, "all"],
        default="all",
    )
    parser.add_argument(
        "--report",
        help="Run one report, e.g. GT01. Default: all GT*.json files.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=ROOT / "data" / "sast_reports",
    )
    parser.add_argument(
        "--snippets-dir",
        type=Path,
        default=ROOT / "data" / "code_snippets",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help="Optional source-code root to extract code around Sonar issues.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Accepted for compatibility; existing result JSON files are always overwritten.",
    )

    args = parser.parse_args()

    # ChromaDB's embedding setup may require the OpenAI API key even
    # when the generation provider is Gemini, Kimi, or Claude.
    if not (
        getattr(settings, "openai_api_key", "")
        or os.getenv("OPENAI_API_KEY")
    ):
        raise SystemExit(
            "[ERROR] OPENAI_API_KEY is required by this branch's "
            "ChromaDB embedding configuration."
        )

    reports = discover_reports(args.reports_dir, args.report)
    provider_names = (
        list(PROVIDERS)
        if args.provider == "all"
        else [args.provider]
    )

    print("Branch 3 — RAG + Code Context")
    print(f"Reports: {len(reports)} | Providers: {', '.join(provider_names)}")
    print(
        f"Mode: {'LIVE GENERATION' if args.execute else 'DRY RUN (no generation calls)'}"
    )

    totals = {"ok": 0, "error": 0, "skip": 0}
    prepared = []

    # Retrieve RAG context once per report and reuse it across providers.
    for path in reports:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            report = SonarReport.model_validate(raw)

            snippets = load_snippets(
                path,
                raw,
                report,
                args.snippets_dir,
            )

            if args.source_root:
                extracted = extract_source_snippets(
                    report,
                    args.source_root,
                )
                snippets = [
                    existing or extracted[i]
                    for i, existing in enumerate(snippets)
                ]

            retrieved = [
                query_knowledge(
                    f"{issue.rule} {issue.message} {' '.join(issue.tags)}"
                )
                for issue in report.issues
            ]

            count = sum(bool(s and s.strip()) for s in snippets)
            docs_count = sum(len(docs) for docs in retrieved)

            print(
                f"[RAG] {path.name}: findings={len(report.issues)}, "
                f"snippets={count}/{len(report.issues)}, docs={docs_count}"
            )

            if not count:
                print(
                    f"[WARN] {path.name}: no source snippets loaded; "
                    "code-context portion will be empty."
                )

            prepared.append((path, report, retrieved, snippets))

        except Exception as exc:
            print(
                f"[ERROR] Preparing {path.name}: "
                f"{type(exc).__name__}: {exc}"
            )
            totals["error"] += 1

    # Execute each provider independently and save into its own folder.
    for provider in provider_names:
        summary = {"ok": 0, "error": 0, "skip": 0}
        provider_folder = output_folder_for(provider)
        out_dir = ROOT / "results" / provider_folder
        out_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"\n{'=' * 54}\n{provider} | model={model_for(provider)} "
            f"| output=results/{provider_folder}"
        )

        for path, report, retrieved, snippets in prepared:
            out = out_dir / f"{path.stem}_LLM.json"
            err = out_dir / f"{path.stem}_ERROR.txt"

            try:
                user_content = build_user_content(
                    report.issues,
                    retrieved,
                    snippets,
                )

                if not args.execute:
                    print(
                        f"[DRY RUN] results/{provider_folder}/"
                        f"{path.stem}_LLM.json: "
                        f"{len(report.issues)} finding(s) prepared"
                    )
                    summary["ok"] += 1
                    continue

                generated = generate(provider, user_content)

                if len(generated.test_cases) != len(report.issues):
                    raise ValueError(
                        f"Expected {len(report.issues)} test cases, "
                        f"got {len(generated.test_cases)}"
                    )

                payload = json.dumps(
                    generated.model_dump(),
                    ensure_ascii=False,
                    indent=2,
                ) + "\n"

                temporary_path = out.with_suffix(out.suffix + ".tmp")
                try:
                    temporary_path.write_text(payload, encoding="utf-8")
                    temporary_path.replace(out)
                finally:
                    if temporary_path.exists():
                        temporary_path.unlink()

                if err.exists():
                    err.unlink()

                print(f"[OK] Saved {out.relative_to(ROOT)}")
                summary["ok"] += 1

            except Exception as exc:
                print(
                    f"[ERROR] {provider}/{path.name}: "
                    f"{type(exc).__name__}: {exc}"
                )
                summary["error"] += 1

                if args.execute:
                    err.write_text(
                        f"Error type: {type(exc).__name__}\n"
                        f"Error message: {exc}\n",
                        encoding="utf-8",
                    )

        for key in totals:
            totals[key] += summary[key]

        print(
            f"[SUMMARY] {provider}: OK={summary['ok']}, "
            f"ERROR={summary['error']}, SKIPPED={summary['skip']}"
        )

    print(
        f"\nFINAL SUMMARY: OK={totals['ok']}, "
        f"ERROR={totals['error']}, SKIPPED={totals['skip']}"
    )

    if not args.execute:
        print(
            "Dry run only. Add --execute to generate results. "
            "ChromaDB retrieval may still call OpenAI embeddings."
        )


if __name__ == "__main__":
    main()
