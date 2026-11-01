import json
from openai import OpenAI
from google import genai
from google.genai import types
from anthropic import Anthropic

from .config import settings
from .schemas import SonarIssue, SecurityTestReport
from .retrieved_doc import RetrievedDoc


_SYSTEM_PROMPT = """You are a senior AppSec/SAST analyst.

Analyze SonarQube findings and create test cases for verification and triage.

Return valid JSON only, matching this structure:
{
    "test_cases": [
        {
            "identificacao": {
                "id_sonarqube": "...",
                "arquivo": "...",
                "linha": 0,
                "severidade_sast": "...",
                "regra": "...",
                "categoria": "..."
            },
            "classificacao": {
                "veredicto": "...",
                "cwe": "...",
                "owasp_top_10": "...",
                "wstg": "...",
                "justificativa": "..."
            },
            "descricao_tecnica": "...",
            "pre_condicoes_para_verificacao": ["..."],
            "passos_de_verificacao": [
                {
                    "passo": "Passo 01",
                    "resultado_esperado_verdadeiro_positivo": "...",
                    "resultado_esperado_falso_positivo": "..."
                }
            ]
        }
    ]
}

Generate exactly one test case per finding, in the same order.
Do not invent findings. Use the supplied CWE and WSTG references
as supporting context, not as evidence that a finding is confirmed.
"""


def _build_finding_block(
    index: int,
    issue: SonarIssue,
    docs: list[RetrievedDoc],
) -> str:
    lines = [
        f"--- Finding {index} ---",
        f"Rule: {issue.rule}",
        f"Severity: {issue.severity}",
        f"Message: {issue.message}",
        f"Component: {issue.component or 'N/A'}",
        f"Line: {issue.line or 'N/A'}",
        f"Tags: {', '.join(issue.tags)}",
    ]

    for doc in docs:
        lines.append(f"\n[{doc.source} Reference: {doc.id}]")
        lines.append(doc.content[:1500])

    return "\n".join(lines)


def _build_user_content(
    issues: list[SonarIssue],
    user_context: str,
    retrieved_per_finding: list[list[RetrievedDoc]],
) -> str:
    blocks = [
        _build_finding_block(i + 1, issue, docs)
        for i, (issue, docs) in enumerate(
            zip(issues, retrieved_per_finding)
        )
    ]

    content = "\n\n".join(blocks)

    if user_context.strip():
        content += (
            "\n\nAdditional context / focus area:\n"
            + user_context.strip()
        )

    return content


def _extract_json(text: str) -> SecurityTestReport:
    """Parse and validate a provider response without changing its contents."""
    text = (text or "").strip()
    if not text:
        raise ValueError("The model returned an empty response.")

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Some providers may wrap an otherwise valid JSON object in a short
        # explanation. Parse only the outer object; Pydantic validates the schema.
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise
        data = json.loads(text[start:end + 1])

    return SecurityTestReport.model_validate(data)


def _source_file(component: str | None) -> str:
    if not component:
        return "N/A"
    # SonarQube components normally use "project-key:path/to/file".
    if re.match(r"^[A-Za-z]:[\\/]", component):
        return component
    project_key, separator, file_path = component.partition(":")
    return file_path if separator and file_path else component


def _source_line(issue: SonarIssue) -> int | str:
    if issue.line is not None:
        return issue.line
    if issue.textRange and issue.textRange.startLine is not None:
        return issue.textRange.startLine
    return "N/A"


def _normalize_source_identification(
    report: SecurityTestReport,
    issues: list[SonarIssue],
) -> SecurityTestReport:
    """Bind source metadata to the corresponding input finding, preserving model analysis."""
    if len(report.test_cases) != len(issues):
        raise ValueError(
            f"Expected {len(issues)} test cases; received {len(report.test_cases)}."
        )

    for test_case, issue in zip(report.test_cases, issues):
        identification = test_case.identificacao
        identification.id_sonarqube = issue.key or "N/A"
        identification.arquivo = _source_file(issue.component)
        identification.linha = _source_line(issue)
        identification.severidade_sast = issue.severity or "N/A"
        identification.regra = issue.rule or "N/A"
        identification.categoria = issue.type or "N/A"

    return report


def _generate_openai(
    user_content: str,
) -> SecurityTestReport:
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("OpenAI returned an empty response.")

    return _extract_json(content)


def _generate_gemini(
    user_content: str,
) -> SecurityTestReport:
    import time
    from google.genai.errors import ServerError

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not configured.")

    client = genai.Client(api_key=settings.google_api_key)

    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=SecurityTestReport,
                ),
            )
            break
        except ServerError:
            if attempt == 3:
                raise

            wait_seconds = 2 ** (attempt + 1)
            print(
                f"Gemini indisponível; tentativa {attempt + 1}/4. "
                f"Nova tentativa em {wait_seconds}s."
            )
            time.sleep(wait_seconds)

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    return _extract_json(response.text)


def _generate_kimi(
    user_content: str,
) -> SecurityTestReport:
    if not settings.kimi_api_key:
        raise ValueError("KIMI_API_KEY is not configured.")

    client = OpenAI(
        api_key=settings.kimi_api_key,
        base_url="https://api.moonshot.ai/v1",
    )

    response = client.chat.completions.create(
        model=settings.kimi_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Kimi returned an empty response.")

    return _extract_json(content)


def _generate_claude(
    user_content: str,
) -> SecurityTestReport:
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured.")

    client = Anthropic(api_key=settings.anthropic_api_key)

    # Use the same prompt and user payload as the other providers, with a
    # provider-native structured-output contract for the shared Pydantic schema.
    response = client.messages.parse(
        model=settings.claude_model,
        max_tokens=8192,
        system=_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_content},
        ],
        output_format=SecurityTestReport,
    )

    parsed = getattr(response, "parsed_output", None)
    if isinstance(parsed, SecurityTestReport):
        return parsed
    if parsed is not None:
        return SecurityTestReport.model_validate(parsed)

    text_blocks = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    if not text_blocks:
        raise ValueError("Claude returned no text content.")

    return _extract_json("\n".join(text_blocks))


def generate_test_cases(
    issues: list[SonarIssue],
    user_context: str,
    retrieved_per_finding: list[list[RetrievedDoc]],
) -> SecurityTestReport:
    if len(issues) != len(retrieved_per_finding):
        raise ValueError(
            "Each finding must have its corresponding RAG results."
        )

    user_content = _build_user_content(
        issues,
        user_context,
        retrieved_per_finding,
    )

    provider = settings.llm_provider.strip().lower()

    generators = {
        "openai": _generate_openai,
        "gemini": _generate_gemini,
        "kimi": _generate_kimi,
        "claude": _generate_claude,
    }

    if provider not in generators:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: {provider}. "
            f"Choose one of: {', '.join(generators)}."
        )

    report = generators[provider](user_content)

    # Keep each output linked to the original finding. Only deterministic source
    # identifiers are normalized; the model's classification and test content
    # remain untouched.
    return _normalize_source_identification(report, issues)
