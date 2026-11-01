"""
Extract CWE entries from the official MITRE CWE XML catalog and write
cleaned .txt files to data/knowledge_base/cwe/, replacing mock content.

Usage:
    python -m scripts.build_cwe_kb
    python -m scripts.build_cwe_kb --cwe-xml cwe/cwec_v4.20.xml
=======
    python -m scripts.build_cwe_kb --abstraction Base,Class
    python -m scripts.build_cwe_kb --cwe-ids 89,79,22
>>>>>>> branch-2-rag-cwe-wstg
"""
import re
import io
import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import sys
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).parent.parent))

OUTPUT_DIR = Path("data/knowledge_base/cwe")
DEFAULT_XML = Path("cwe/cwec_v4.20.xml")
NS = {"cwe": "http://cwe.mitre.org/cwe-7"}

# CWEs to extract — extend this list to add more entries
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
                xml_members = [name for name in archive.namelist() if name.lower().endswith(".xml")]
                if not xml_members:
                    print(f"No XML file found in archive: {url}")
                    continue

                preferred = next((name for name in xml_members if Path(name).name == xml_path.name), None)
                member = preferred or xml_members[0]

                with archive.open(member) as source, xml_path.open("wb") as target:
                    target.write(source.read())

            print(f"CWE XML downloaded to: {xml_path}")
            return True
        except (HTTPError, URLError, TimeoutError, zipfile.BadZipFile) as exc:
            print(f"Download failed from {url}: {exc}")

    return False


def _text(element) -> str:
    """Flatten an XML element's text content, stripping inner tags and excess whitespace."""
    desc_el  = _find(weakness_el, "cwe:Description")
    ext_el   = _find(weakness_el, "cwe:Extended_Description")
    desc     = _text(desc_el)
    ext_desc = _text(ext_el)

    # Likelihood
    likely_el = _find(weakness_el, "cwe:Likelihood_Of_Exploit")
    likelihood = _text(likely_el) if likely_el is not None else ""

    # Applicable platforms
    platforms: list[str] = []
    for lang in _findall(weakness_el, "cwe:Applicable_Platforms/cwe:Language"):
        val = lang.get("Name") or lang.get("Class", "")
        if val:
            platforms.append(val)
    for tech in _findall(weakness_el, "cwe:Applicable_Platforms/cwe:Technology"):
        val = tech.get("Name") or tech.get("Class", "")
        if val:
            platforms.append(val)

    # Common consequences
    mitigations: list[str] = []
    for mit in _findall(weakness_el, "cwe:Potential_Mitigations/cwe:Mitigation"):
        phase_els = _findall(mit, "cwe:Phase")
        phases    = ", ".join(_text(p) for p in phase_els)
        mit_desc  = _text(_find(mit, "cwe:Description"))
        if mit_desc:
            prefix = f"[{phases}] " if phases else ""
            mitigations.append(f"- {prefix}{mit_desc}")
    mitigations_text = "\n".join(mitigations)
    if len(mitigations_text) > MITIGATIONS_MAX_CHARS:
        mitigations_text = mitigations_text[:MITIGATIONS_MAX_CHARS].rsplit('\n', 1)[0] + "\n[...truncated]"

    # Detection methods
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
    parser.add_argument("--cwe-xml", default=str(DEFAULT_XML),
                        help=f"Path to CWE XML catalog (default: {DEFAULT_XML})")
    parser.add_argument("--no-download", action="store_true",
                        help="Do not download CWE XML automatically when missing.")
    args = parser.parse_args()

<<<<<<< HEAD
    xml_path = Path(args.cwe_xml)
    if not xml_path.exists():
        print(f"CWE XML not found locally: {xml_path}")
        if args.no_download or not _download_cwe_xml(xml_path):
            print(f"Error: CWE XML not found: {xml_path}")
            sys.exit(1)

    print(f"Parsing {xml_path} ({xml_path.stat().st_size // 1024 // 1024} MB)...")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Build lookup: ID → element
        el = weakness_map.get(cwe_id)
        if el is None:
            print(f"  MISSING  CWE-{cwe_id}")
            fail += 1
            continue
        text = extract_weakness(el)
        out  = OUTPUT_DIR / f"CWE-{cwe_id}.txt"
        out.write_text(text, encoding="utf-8")
        print(f"  OK  CWE-{cwe_id}  ({len(text):,} chars)  ->  {out.name}")
        ok += 1

    print(f"\n{ok} extracted, {fail} missing.")


if __name__ == "__main__":
    main()
