"""LLM provider adapters for direct SAST test-case generation."""
import json

from anthropic import Anthropic
from openai import OpenAI

from .config import settings
from .schemas import SecurityTestReport, SonarIssue


_SYSTEM_PROMPT = """You are a senior AppSec/SAST analyst.

Analyze the supplied SonarQube findings and create one security test case per
finding, preserving the input order. Do not invent findings. Return valid JSON
matching this schema:
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
}"""


def _build_user_content(issues: list[SonarIssue]) -> str:
    findings_payload = [
        {
            "index": index,
            "key": issue.key,
            "rule": issue.rule,
            "severity": issue.severity,
            "message": issue.message,
            "component": issue.component,
            "line": issue.line,
            "type": issue.type,
            "tags": issue.tags,
        }
        for index, issue in enumerate(issues, start=1)
    ]
    return (
        "SAST Findings:\n"
        + json.dumps(findings_payload, indent=2, ensure_ascii=False)
    )


def _extract_json(text: str) -> SecurityTestReport:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return SecurityTestReport.model_validate_json(text)


def _generate_openai(user_content: str) -> SecurityTestReport:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.beta.chat.completions.parse(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format=SecurityTestReport,
    )
    choice = response.choices[0]
    if choice.message.refusal:
        raise ValueError(f"OpenAI refused the request: {choice.message.refusal}")
    if choice.message.parsed is None:
        raise ValueError("OpenAI did not return a structured response.")
    return choice.message.parsed


def _generate_kimi(user_content: str) -> SecurityTestReport:
    if not settings.kimi_api_key:
        raise ValueError("KIMI_API_KEY is not configured.")
    if not settings.kimi_model:
        raise ValueError("KIMI_MODEL is not configured.")
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
        temperature=1,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Kimi returned an empty response.")
    return _extract_json(content)


def _generate_gemini(user_content: str) -> SecurityTestReport:
    from google import genai

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not configured.")
    if not settings.gemini_model:
        raise ValueError("GEMINI_MODEL is not configured.")
    client = genai.Client(api_key=settings.google_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=_SYSTEM_PROMPT + "\n\n" + user_content,
        config={
            "response_mime_type": "application/json",
            "response_schema": SecurityTestReport,
            "temperature": 0,
        },
    )
    if not response.text:
        raise ValueError("Gemini returned an empty response.")
    return _extract_json(response.text)


def _generate_claude(user_content: str) -> SecurityTestReport:
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured.")
    if not settings.claude_model:
        raise ValueError("CLAUDE_MODEL is not configured.")
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=8192,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
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
    provider: str | None = None,
) -> SecurityTestReport:
    """Generate one test case per finding using the selected provider."""
    selected_provider = (
        provider.strip().lower()
        if provider
        else settings.llm_provider.strip().lower()
    )
    generators = {
        "openai": _generate_openai,
        "gemini": _generate_gemini,
        "kimi": _generate_kimi,
        "claude": _generate_claude,
    }
    if selected_provider not in generators:
        raise ValueError(
            "Invalid provider. Choose: openai, gemini, kimi, or claude."
        )

    report = generators[selected_provider](_build_user_content(issues))
    if len(report.test_cases) != len(issues):
        raise ValueError(
            "The LLM returned "
            f"{len(report.test_cases)} test cases for {len(issues)} findings."
        )
    return report
