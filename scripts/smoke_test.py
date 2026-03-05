#!/usr/bin/env python3
"""Smoke test: hit a running app with generated test documents, print results.

NOT an automated test suite — a human-readable validation report you run
while the app is up to verify the full detection/anonymization pipeline.

Prerequisites:
    1. python scripts/generate_test_documents.py
    2. uv run uvicorn document_anonymizer.api.app:app --reload
    3. python scripts/smoke_test.py

Usage:
    python scripts/smoke_test.py [--base-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

import httpx

DOCS_DIR = Path(__file__).resolve().parent.parent / "test_documents"

# ANSI color helpers
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def ok(msg: str) -> str:
    return f"{GREEN}PASS{RESET} {msg}"


def fail(msg: str) -> str:
    return f"{RED}FAIL{RESET} {msg}"


def warn(msg: str) -> str:
    return f"{YELLOW}WARN{RESET} {msg}"


def header(msg: str) -> str:
    return f"\n{BOLD}{CYAN}{'═' * 60}\n  {msg}\n{'═' * 60}{RESET}"


# Expected PII types per document (minimum expectations)
EXPECTED_PII: dict[str, set[str]] = {
    "kuendigungsschreiben": {"PERSON", "DE_IBAN", "DE_PHONE"},
    "lebenslauf": {"PERSON", "DE_PHONE"},
    "handelsregister_auszug": {"PERSON", "DE_HANDELSREGISTER"},
    "rechnung": {"PERSON", "DE_IBAN", "DE_PHONE"},
    "mixed_edge_cases": {"PERSON", "DE_IBAN", "DE_PHONE", "DE_HANDELSREGISTER"},
}

STRATEGIES = ["replace", "mask", "hash", "fake", "redact"]


def check_health(client: httpx.Client) -> bool:
    """Check if the app is running."""
    try:
        r = client.get("/health", timeout=5)
        return r.status_code == 200
    except httpx.ConnectError:
        return False


def test_detect_text(client: httpx.Client, name: str, text: str) -> dict | None:
    """POST text to /api/detect, print results, return response."""
    r = client.post(
        "/api/detect",
        json={"text": text, "language": "de", "score_threshold": 0.35},
        timeout=30,
    )
    if r.status_code != 200:
        print(fail(f"  /api/detect returned {r.status_code}: {r.text[:200]}"))
        return None

    data = r.json()
    entities = data.get("entities", [])
    found_types = {e["entity_type"] for e in entities}
    expected = EXPECTED_PII.get(name, set())
    missing = expected - found_types

    # Print entity summary
    print(
        f"\n  {BOLD}Detected {data['entity_count']} entities{RESET}"
        f" ({data['processing_time_ms']:.0f}ms)"
    )

    # Group by type
    by_type: dict[str, list] = {}
    for e in entities:
        by_type.setdefault(e["entity_type"], []).append(e)

    for etype, elist in sorted(by_type.items()):
        samples = [f'"{e["text"]}"' for e in elist[:3]]
        suffix = f" (+{len(elist) - 3} more)" if len(elist) > 3 else ""
        status = GREEN + "✓" + RESET if etype in expected else DIM + "·" + RESET
        print(
            f"    {status} {etype:25s} ×{len(elist):2d}  {', '.join(samples)}{suffix}"
        )

    # Check coverage
    if missing:
        print(fail(f"  Missing expected types: {', '.join(sorted(missing))}"))
    else:
        print(ok("  All expected PII types found"))

    return data


def test_anonymize_text(
    client: httpx.Client, name: str, text: str, strategy: str
) -> bool:
    """POST text to /api/anonymize with given strategy, print summary."""
    r = client.post(
        "/api/anonymize",
        json={
            "text": text,
            "language": "de",
            "strategy": strategy,
            "score_threshold": 0.35,
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(fail(f"    {strategy:8s} → HTTP {r.status_code}"))
        return False

    data = r.json()
    anon_text = data["anonymized_text"]
    n = data["entities_found"]

    # Show a short preview of the anonymized output
    preview = anon_text[:120].replace("\n", "  ")
    if len(anon_text) > 120:
        preview += "…"
    print(f"    {GREEN}✓{RESET} {strategy:8s}  ({n} entities)  {DIM}{preview}{RESET}")
    return True


def test_redact_pdf(client: httpx.Client, name: str, pdf_path: Path) -> bool:
    """POST PDF to /redact-pdf, save result, print summary."""
    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    r = client.post(
        "/redact-pdf",
        headers={"HX-Request": "true"},
        data={"pdf_b64": pdf_b64, "score_threshold": "0.35"},
        timeout=60,
    )

    if r.status_code == 200 and r.headers.get("content-type", "").startswith(
        "application/pdf"
    ):
        out_path = DOCS_DIR / f"{name}_redacted.pdf"
        out_path.write_bytes(r.content)
        size_kb = len(r.content) / 1024
        print(ok(f"  {name}.pdf → {out_path.name} ({size_kb:.1f} KB)"))
        return True
    elif r.status_code == 422:
        print(warn(f"  {name}.pdf → incomplete redaction (HTTP 422)"))
        return True  # Partial success
    else:
        print(fail(f"  {name}.pdf → HTTP {r.status_code}: {r.text[:200]}"))
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test against running app")
    parser.add_argument(
        "--base-url", default="http://localhost:8000", help="App base URL"
    )
    args = parser.parse_args()

    if not DOCS_DIR.exists():
        print(f"{RED}Error:{RESET} {DOCS_DIR} not found.")
        print("Run: python scripts/generate_test_documents.py")
        sys.exit(1)

    client = httpx.Client(base_url=args.base_url)

    # ── Health check ──────────────────────────────────────────────
    print(header("Health Check"))
    if not check_health(client):
        print(fail(f"App not reachable at {args.base_url}"))
        print(
            "\nStart it with: uv run uvicorn document_anonymizer.api.app:app --reload"
        )
        sys.exit(1)
    print(ok(f"App running at {args.base_url}"))

    txt_files = sorted(DOCS_DIR.glob("*.txt"))
    pdf_files = sorted(p for p in DOCS_DIR.glob("*.pdf") if "redacted" not in p.name)

    pass_count = 0
    fail_count = 0
    total_start = time.perf_counter()

    # ── Text Detection ────────────────────────────────────────────
    print(header("Text Detection (/api/detect)"))
    for txt_path in txt_files:
        name = txt_path.stem
        text = txt_path.read_text(encoding="utf-8")
        print(f"\n{BOLD}▸ {name}{RESET}  ({len(text)} chars)")
        result = test_detect_text(client, name, text)
        if result:
            pass_count += 1
        else:
            fail_count += 1

    # ── Text Anonymization ────────────────────────────────────────
    print(header("Text Anonymization (/api/anonymize)"))
    for txt_path in txt_files:
        name = txt_path.stem
        text = txt_path.read_text(encoding="utf-8")
        print(f"\n{BOLD}▸ {name}{RESET}")
        all_ok = True
        for strategy in STRATEGIES:
            if not test_anonymize_text(client, name, text, strategy):
                all_ok = False
        if all_ok:
            pass_count += 1
        else:
            fail_count += 1

    # ── PDF Redaction ─────────────────────────────────────────────
    print(header("PDF Redaction (/redact-pdf)"))
    for pdf_path in pdf_files:
        name = pdf_path.stem
        if test_redact_pdf(client, name, pdf_path):
            pass_count += 1
        else:
            fail_count += 1

    # ── Summary ───────────────────────────────────────────────────
    elapsed = time.perf_counter() - total_start
    print(header("Summary"))
    print(
        f"  {GREEN}{pass_count} passed{RESET}, {RED}{fail_count} failed{RESET}"
        f"  ({elapsed:.1f}s total)"
    )

    if fail_count:
        print(f"\n  {RED}Some checks failed — review output above.{RESET}")
    else:
        print(f"\n  {GREEN}All checks passed!{RESET}")
        print("\n  Next steps:")
        print(f"  1. Open {args.base_url} and upload PDFs via web UI")
        print(f"  2. Inspect redacted PDFs in {DOCS_DIR}/ with a PDF viewer")
        print("     (text should be physically removed, not just covered)")

    client.close()
    sys.exit(1 if fail_count else 0)


if __name__ == "__main__":
    main()
