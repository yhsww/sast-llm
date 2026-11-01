from openai import OpenAI
from google import genai
from google.genai import types
from anthropic import Anthropic

from .config import settings
from .schemas import SonarIssue, SecurityTestReport
<<<<<<< HEAD
from .chroma_service import RetrievedDoc
=======
from .retrieved_doc import RetrievedDoc
>>>>>>> branch-2-rag-cwe-wstg


_SYSTEM_PROMPT = """You are a senior AppSec/SAST analyst.

<<<<<<< HEAD
Your task is to analyze a SonarQube alert and create a test case for verification and triage based on the fields below.

Return valid JSON only.

The JSON must match this structure exactly:
=======
Analyze SonarQube findings and create test cases for verification and triage.

Return valid JSON only, matching this structure:
>>>>>>> branch-2-rag-cwe-wstg
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

<<<<<<< HEAD
Do not invent findings. Generate one test case per finding, in the same order."""
=======
Generate exactly one test case per finding, in the same order.
Do not invent findings. Use the supplied CWE and WSTG references
as supporting context, not as evidence that a finding is confirmed.
"""
>>>>>>> branch-2-rag-cwe-wstg


def _build_finding_block(
    index: int,
    issue: SonarIssue,
    docs: list[RetrievedDoc],
    code_snippet: str | None,
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

<<<<<<< HEAD
    if code_snippet and code_snippet.strip():
        lines.append("\n[Vulnerable Source Code]")
        lines.append(f"```\n{code_snippet.strip()}\n```")

    for doc in docs:
        lines.append(f"\n[{doc.source} Reference: {doc.id}]")
        lines.append(doc.content[:1500])  # cap per-doc to control token usage
=======
    for doc in docs:
        lines.append(f"\n[{doc.source} Reference: {doc.id}]")
        lines.append(doc.content[:1500])
>>>>>>> branch-2-rag-cwe-wstg

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
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    data = json.loads(text)
    return SecurityTestReport.model_validate(data)


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
                f"Gemini unvailabe; try {attempt + 1}/4. "
                f"Try again in {wait_seconds}s."
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

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=8192,
        system=_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_content},
        ],
    )

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
<<<<<<< HEAD
    code_snippets: list[str | None],
) -> SecurityTestReport:
    # Pad snippets list to match issues length (missing entries treated as None)
    snippets = list(code_snippets) + [None] * max(0, len(issues) - len(code_snippets))

    blocks = [
        _build_finding_block(i + 1, issue, docs, snippets[i])
        for i, (issue, docs) in enumerate(zip(issues, retrieved_per_finding))
    ]

    user_content = "\n\n".join(blocks)
    if user_context.strip():
        user_content += f"\n\nAdditional context / focus area:\n{user_context.strip()}"

    response = _client.beta.chat.completions.parse(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format=SecurityTestReport,
=======
) -> SecurityTestReport:
    if len(issues) != len(retrieved_per_finding):
        raise ValueError(
            "Each finding must have its corresponding RAG results."
        )

    user_content = _build_user_content(
        issues,
        user_context,
        retrieved_per_finding,
>>>>>>> branch-2-rag-cwe-wstg
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

    if len(report.test_cases) != len(issues):
        raise ValueError(
            f"{provider} returned {len(report.test_cases)} test cases "
            f"for {len(issues)} findings."
        )

    return report
