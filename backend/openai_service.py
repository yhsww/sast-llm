
import json

from openai import OpenAI
from google import genai
from anthropic import Anthropic

from .config import settings
from .schemas import SonarIssue, SecurityTestReport


_SYSTEM_PROMPT = """You are a senior AppSec/SAST analyst.

Your task is to analyze a SonarQube alert and create a test case for verification and triage based on the fields below.

Return valid JSON only.

The JSON must match this structure exactly:
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

Do not invent findings. Generate one test case per finding, in the same order."""



def _build_user_content(issues: list[SonarIssue]) -> str:
    findings_payload = [
        {
            "index": i + 1,
            "key": issue.key,
            "rule": issue.rule,
            "severity": issue.severity,
            "message": issue.message,
            "component": issue.component,
            "line": issue.line,
            "type": issue.type,
            "tags": issue.tags,
        }
        for i, issue in enumerate(issues)
    ]

    return (
        "SAST Findings:\n"
        + json.dumps(findings_payload, indent=2, ensure_ascii=False)
    )


def _generate_openai(user_content: str) -> SecurityTestReport:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY não configurada.")

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

    if choice.finish_reason == "refusal":
        raise ValueError(f"LLM refused: {choice.message.refusal}")

    if choice.message.parsed is None:
        raise ValueError("OpenAI não retornou uma resposta estruturada.")

    return choice.message.parsed


def _generate_kimi(user_content: str) -> SecurityTestReport:
    if not settings.kimi_api_key:
        raise ValueError("KIMI_API_KEY não configurada.")
    if not settings.kimi_model:
        raise ValueError("KIMI_MODEL não configurado.")

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
        temperature=0,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Kimi retornou uma resposta vazia.")

    return SecurityTestReport.model_validate_json(content)


def _generate_gemini(user_content: str) -> SecurityTestReport:
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY não configurada.")
    if not settings.gemini_model:
        raise ValueError("GEMINI_MODEL não configurado.")

    client = genai.Client(api_key=settings.google_api_key)

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=(
            _SYSTEM_PROMPT
            + "\n\n"
            + user_content
        ),
        config={
            "response_mime_type": "application/json",
            "response_schema": SecurityTestReport,
            "temperature": 0,
        },
    )

    if not response.text:
        raise ValueError("Gemini retornou uma resposta vazia.")

    return SecurityTestReport.model_validate_json(response.text)


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
        messages=[
            {
                "role": "user",
                "content": user_content,
            }
        ],
    )

    text_blocks = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]

    if not text_blocks:
        raise ValueError("Claude returned no text content.")

    return SecurityTestReport.model_validate_json(text_blocks[0])


def generate_test_cases(
    issues: list[SonarIssue],
    provider: str | None = None,
) -> SecurityTestReport:
    user_content = _build_user_content(issues)

    provider = (
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

    if provider not in generators:
        raise ValueError(
            "Provedor inválido. Use: openai, gemini, kimi ou claude."
        )

    return generators[provider](user_content)

