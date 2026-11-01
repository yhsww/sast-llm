"""
Extract a fixed set of CWE entries from the official MITRE CWE XML catalog.
Outputs cleaned text files to data/knowledge_base/cwe/.
"""
import argparse
import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

OUTPUT_DIR = Path("data/knowledge_base/cwe")
DEFAULT_XML = Path("cwe/cwec_v4.20.xml")
NS = {"cwe": "http://cwe.mitre.org/cwe-7"}

# Fixed CWE set used by this experiment.
CWE_IDS = [
    "89",   # SQL Injection
    "79",   # XSS
    "798",  # Hard-coded Credentials
    "22",   # Path Traversal
    "287",  # Improper Authentication
    "611",  # XXE
    "502",  # Deserialization
    "918",  # SSRF
    "434",  # Unrestricted File Upload
    "307",  # Brute Force / Improper Auth Attempts
]
MITIGATIONS_MAX_CHARS = 1500
CONSEQUENCES_MAX_ITEMS = 5


def _download_cwe_xml(xml_path: Path) -> bool:
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    candidates = [
        f"https://cwe.mitre.org/data/xml/{xml_path.name}.zip",
        "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip",
    ]

    for url in candidates:
        try:
            print(f"Downloading CWE XML from: {url}")
            with urlopen(url, timeout=60) as response:
                payload = response.read()

            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                xml_members = [
                    name for name in archive.namelist()
                    if name.lower().endswith(".xml")
                ]
                if not xml_members:
                    print(f"No XML file found in archive: {url}")
                    continue
                preferred = next(
                    (name for name in xml_members if Path(name).name == xml_path.name),
                    None,
                )
                member = preferred or xml_members[0]
                with archive.open(member) as source, xml_path.open("wb") as target:
                    target.write(source.read())

            print(f"CWE XML downloaded to: {xml_path}")
            return True
        except (HTTPError, URLError, TimeoutError, zipfile.BadZipFile) as exc:
            print(f"Download failed from {url}: {exc}")
    return False


def _text(element) -> str:
    """Flatten an XML element's text content and normalize whitespace."""
    if element is None:
        return ""
    raw = ET.tostring(element, encoding="unicode", method="text")
    return re.sub(r"\s+", " ", raw).strip()


def _find(element, xpath: str):
    return element.find(xpath, NS)


def _findall(element, xpath: str):
    return element.findall(xpath, NS)


def extract_weakness(weakness_el) -> str:
    cwe_id = weakness_el.get("ID", "")
    name = weakness_el.get("Name", "")
    header = f"CWE-{cwe_id}: {name}"

    desc = _text(_find(weakness_el, "cwe:Description"))
    ext_desc = _text(_find(weakness_el, "cwe:Extended_Description"))
    likely_el = _find(weakness_el, "cwe:Likelihood_Of_Exploit")
    likelihood = _text(likely_el) if likely_el is not None else ""

    platforms: list[str] = []
    for lang in _findall(weakness_el, "cwe:Applicable_Platforms/cwe:Language"):
        value = lang.get("Name") or lang.get("Class", "")
        if value:
            platforms.append(value)
    for tech in _findall(weakness_el, "cwe:Applicable_Platforms/cwe:Technology"):
        value = tech.get("Name") or tech.get("Class", "")
        if value:
            platforms.append(value)

    consequences: list[str] = []
    for item in _findall(weakness_el, "cwe:Common_Consequences/cwe:Consequence"):
        scope = ", ".join(_text(s) for s in _findall(item, "cwe:Scope"))
        impact = ", ".join(_text(i) for i in _findall(item, "cwe:Impact"))
        note = _text(_find(item, "cwe:Note"))
        line = f"- {scope}: {impact}"
        if note:
            line += f" — {note[:200]}"
        consequences.append(line)
    consequences = consequences[:CONSEQUENCES_MAX_ITEMS]

    mitigations: list[str] = []
    for item in _findall(weakness_el, "cwe:Potential_Mitigations/cwe:Mitigation"):
        phases = ", ".join(_text(p) for p in _findall(item, "cwe:Phase"))
        description = _text(_find(item, "cwe:Description"))
        if description:
            prefix = f"[{phases}] " if phases else ""
            mitigations.append(f"- {prefix}{description}")
    mitigations_text = "\n".join(mitigations)
    if len(mitigations_text) > MITIGATIONS_MAX_CHARS:
        mitigations_text = (
            mitigations_text[:MITIGATIONS_MAX_CHARS].rsplit("\n", 1)[0]
            + "\n[...truncated]"
        )

    detection: list[str] = []
    for item in _findall(weakness_el, "cwe:Detection_Methods/cwe:Detection_Method"):
        method = _text(_find(item, "cwe:Method"))
        description = _text(_find(item, "cwe:Description"))
        if description:
            prefix = f"[{method}] " if method else ""
            detection.append(f"- {prefix}{description[:300]}")

    parts = [header, ""]
    if likelihood:
        parts += [f"Likelihood of Exploit: {likelihood}", ""]
    if platforms:
        parts += [f"Applicable Platforms: {', '.join(platforms)}", ""]
    if desc:
        parts += ["## Description", desc, ""]
    if ext_desc:
        parts += ["## Extended Description", ext_desc[:800], ""]
    if consequences:
        parts += ["## Common Consequences"] + consequences + [""]
    if mitigations_text:
        parts += ["## Potential Mitigations", mitigations_text, ""]
    if detection:
        parts += ["## Detection Methods"] + detection[:4] + [""]

    return "\n".join(parts).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cwe-xml",
        default=str(DEFAULT_XML),
        help=f"Path to CWE XML catalog (default: {DEFAULT_XML})",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Do not download CWE XML automatically when missing.",
    )
    args = parser.parse_args()

    xml_path = Path(args.cwe_xml)
    if not xml_path.exists():
        print(f"CWE XML not found locally: {xml_path}")
        if args.no_download or not _download_cwe_xml(xml_path):
            print(f"Error: CWE XML not found: {xml_path}")
            sys.exit(1)

    print(f"Parsing {xml_path} ({xml_path.stat().st_size // 1024 // 1024} MB)...")
    root = ET.parse(xml_path).getroot()
    weakness_map = {
        item.get("ID", ""): item
        for item in root.findall(".//cwe:Weakness", NS)
    }
    print(f"  {len(weakness_map)} weaknesses in catalog.\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    for cwe_id in CWE_IDS:
        element = weakness_map.get(cwe_id)
        if element is None:
            print(f"  MISSING  CWE-{cwe_id}")
            fail += 1
            continue
        content = extract_weakness(element)
        output = OUTPUT_DIR / f"CWE-{cwe_id}.txt"
        output.write_text(content, encoding="utf-8")
        print(f"  OK  CWE-{cwe_id}  ({len(content):,} chars)  ->  {output.name}")
        ok += 1

    print(f"\n{ok} extracted, {fail} missing.")


if __name__ == "__main__":
    main()
