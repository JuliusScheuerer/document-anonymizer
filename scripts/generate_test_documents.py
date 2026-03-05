#!/usr/bin/env python3
"""Generate realistic German test documents with known PII for manual validation.

Creates text and PDF files in test_documents/ covering all supported PII types:
PERSON, DE_DATE, DE_ADDRESS, DE_IBAN, DE_TAX_ID, DE_PHONE, DE_ID_CARD,
DE_HANDELSREGISTER

Usage:
    python scripts/generate_test_documents.py
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "test_documents"

# ── Document content ────────────────────────────────────────────────────────

DOCUMENTS: dict[str, str] = {
    "kuendigungsschreiben": """\
Maria Schneider
Hauptstraße 127
80331 München

Telefon: +49 89 23456789

An die
Muster Versicherung AG
Kundenservice
Postfach 1234
60001 Frankfurt am Main

München, den 15.01.2025

Betreff: Kündigung meines Vertrages Nr. VN-2024-887431

Sehr geehrte Damen und Herren,

hiermit kündige ich meinen Versicherungsvertrag Nr. VN-2024-887431
fristgerecht zum 31.03.2025.

Bitte überweisen Sie etwaige Rückerstattungen auf folgendes Konto:

Kontoinhaber: Maria Schneider
IBAN: DE89 3704 0044 0532 0130 00
BIC: COBADEFFXXX

Meine Steuer-Identifikationsnummer lautet: 65 929 970 489

Bitte senden Sie mir eine schriftliche Bestätigung der Kündigung
an die oben genannte Adresse.

Mit freundlichen Grüßen,

Maria Schneider
""",
    "lebenslauf": """\
LEBENSLAUF

Persönliche Daten
──────────────────────────────────────────
Name:           Dr. Thomas Weber
Geburtsdatum:   23.05.1982
Geburtsort:     Stuttgart
Anschrift:      Friedrichstraße 42, 10117 Berlin
Telefon:        +49 30 98765432
Mobiltelefon:   0171 2345678
Personalausweis: T220001293

Berufserfahrung
──────────────────────────────────────────
seit 01.09.2018   Senior Software Architect
                  Deutsche Telekom AG, Bonn

01.04.2012 -      Software Engineer
31.08.2018        SAP SE, Walldorf

01.10.2008 -      Junior Developer
31.03.2012        Siemens AG, München

Ausbildung
──────────────────────────────────────────
01.10.2002 -      Informatik (Diplom)
30.09.2008        Technische Universität München

01.08.1998 -      Allgemeine Hochschulreife
30.06.2002        Friedrich-Schiller-Gymnasium Stuttgart

Sprachkenntnisse
──────────────────────────────────────────
Deutsch (Muttersprache), Englisch (fließend), Französisch (Grundkenntnisse)

Berlin, den 10.03.2025

Dr. Thomas Weber
""",
    "handelsregister_auszug": """\
AMTSGERICHT MÜNCHEN
Handelsregister Abteilung B

─────────────────────────────────────────────────
AKTUELLER AUSDRUCK                    14.02.2025
─────────────────────────────────────────────────

HRB 234567

Firma:          Innovativ Software Solutions GmbH
Sitz:           München
Anschrift:      Leopoldstraße 89, 80802 München

Gegenstand:     Entwicklung und Vertrieb von Software

Stammkapital:   25.000,00 EUR

Geschäftsführer:
  1. Prof. Dr. Andreas Müller, München
     bestellt am 15.06.2019
  2. Claudia Fischer, Berlin
     bestellt am 01.01.2022

Prokura:
  Dr. Stefan Braun, Hamburg
  Einzelprokura, eingetragen am 01.03.2023

Gesellschafter:
  Prof. Dr. Andreas Müller     60%
  Claudia Fischer              40%

Letzte Eintragung:             22.11.2024
Registerzeichen:               HRB 234567, Amtsgericht München

Dieser Ausdruck wurde am 14.02.2025 erstellt.
""",
    "rechnung": """\
═══════════════════════════════════════════════
              WEBDESIGN SCHMITT
         Inh. Klaus Schmitt
═══════════════════════════════════════════════

Webdesign Schmitt | Bergstraße 15 | 69115 Heidelberg
Telefon: 06221 334455
Steuernummer: 32/456/12345

                                 Heidelberg, 28.02.2025

Rechnungsempfänger:
Frau Dr. Sabine Hartmann
Kurze Gasse 7
69117 Heidelberg

──────────────────────────────────────────────
RECHNUNG Nr. 2025-0042
──────────────────────────────────────────────

Leistungszeitraum: 01.01.2025 - 28.02.2025

Pos.  Beschreibung                    Menge    Preis      Gesamt
────  ─────────────────────────────   ─────   ──────     ───────
  1   Website-Redesign (Konzept)        1     2.500,00   2.500,00
  2   Frontend-Entwicklung             40 h      95,00   3.800,00
  3   CMS-Integration                  16 h      95,00   1.520,00
  4   SEO-Optimierung                   8 h      85,00     680,00
                                                       ──────────
                                          Nettobetrag:   8.500,00
                                        + 19% MwSt.:     1.615,00
                                                       ──────────
                                   Gesamtbetrag EUR:    10.115,00

Zahlungsziel: 14 Tage nach Rechnungseingang

Bankverbindung:
Kontoinhaber: Klaus Schmitt
IBAN: DE75 5121 0800 1245 1261 99
BIC: DDBKDEFF

Vielen Dank für Ihr Vertrauen!

Klaus Schmitt
""",
    "mixed_edge_cases": """\
TESTDOKUMENT: Alle PII-Typen auf engem Raum
════════════════════════════════════════════════

Herr Max Mustermann (Steuer-ID: 02 476 010 677) erreichen Sie unter
+49 172 9876543 oder unter seiner Adresse Unter den Linden 1, 10117 Berlin.
Seine IBAN lautet DE02 1001 0010 0987 6543 21, Personalausweis: L01X00T47.

Am 01.04.2024 gründete Frau Anna Becker (Tel.: 030 44556677) die Firma
Becker Consulting GmbH, eingetragen beim Amtsgericht Charlottenburg
unter HRB 123456 B. Geschäftsadresse: Kurfürstendamm 200, 10719 Berlin.

Dr. med. Heinrich von Treskow, geboren am 30.12.1975, wohnhaft in
Schillerstraße 33, 99423 Weimar, Steuer-ID 57 549 285 017, IBAN:
DE44 8205 0000 3012 3456 78, Telefon: +49 3643 123456,
Personalausweis-Nr.: T220001293.

Kontaktliste vom 15.03.2025:
  1. Maria Schneider     +49 89 23456789     Hauptstraße 127, 80331 München
  2. Klaus Schmitt       06221 334455        Bergstraße 15, 69115 Heidelberg
  3. Claudia Fischer     +49 40 77889900     Elbchaussee 12, 22763 Hamburg

Handelsregister-Einträge:
  - HRB 234567, Amtsgericht München (Innovativ Software Solutions GmbH)
  - HRB 98765, Amtsgericht Frankfurt (Deutsche Beratung AG)
  - HRA 5432, Amtsgericht Hamburg (Schmitt & Partner KG)

Bankverbindungen:
  IBAN: DE89 3704 0044 0532 0130 00 (Schneider)
  IBAN: DE75 5121 0800 1245 1261 99 (Schmitt)

Nächster Termin: 22.04.2025 um 14:00 Uhr
Letzte Änderung: 10.03.2025
""",
}


def create_text_files() -> list[Path]:
    """Write all documents as .txt files."""
    paths = []
    for name, content in DOCUMENTS.items():
        path = OUTPUT_DIR / f"{name}.txt"
        path.write_text(content, encoding="utf-8")
        paths.append(path)
        print(f"  [txt] {path.name}")
    return paths


def _render_text_to_pdf(text: str, *, title: str = "") -> bytes:
    """Render multi-line text into a formatted PDF using PyMuPDF."""
    doc = fitz.open()
    lines = text.split("\n")

    # Page layout constants
    margin_x = 56
    margin_top = 64
    margin_bottom = 60
    line_height = 14
    fontsize = 10
    page_width = 595  # A4
    page_height = 842  # A4

    page = doc.new_page(width=page_width, height=page_height)
    y = margin_top

    for line in lines:
        if y + line_height > page_height - margin_bottom:
            # New page
            page = doc.new_page(width=page_width, height=page_height)
            y = margin_top

        page.insert_text(
            (margin_x, y),
            line,
            fontsize=fontsize,
            fontname="helv",
        )
        y += line_height

    if title:
        doc.set_metadata({"title": title})

    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return pdf_bytes


def create_pdf_files() -> list[Path]:
    """Render all documents as formatted PDFs."""
    paths = []
    for name, content in DOCUMENTS.items():
        pdf_bytes = _render_text_to_pdf(content, title=name.replace("_", " ").title())
        path = OUTPUT_DIR / f"{name}.pdf"
        path.write_bytes(pdf_bytes)
        paths.append(path)
        print(f"  [pdf] {path.name}")
    return paths


def create_multipage_pdf() -> Path:
    """Create a multi-page PDF combining all documents to test page boundaries."""
    doc = fitz.open()

    margin_x = 56
    margin_top = 64
    margin_bottom = 60
    line_height = 14
    fontsize = 10
    page_width = 595
    page_height = 842

    for doc_name, content in DOCUMENTS.items():
        # Section header page
        page = doc.new_page(width=page_width, height=page_height)
        header = f"─── {doc_name.upper().replace('_', ' ')} ───"
        page.insert_text(
            (margin_x, margin_top),
            header,
            fontsize=14,
            fontname="helv",
        )

        y = margin_top + 30
        for line in content.split("\n"):
            if y + line_height > page_height - margin_bottom:
                page = doc.new_page(width=page_width, height=page_height)
                y = margin_top
            page.insert_text(
                (margin_x, y),
                line,
                fontsize=fontsize,
                fontname="helv",
            )
            y += line_height

    path = OUTPUT_DIR / "alle_dokumente_mehrseitig.pdf"
    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    path.write_bytes(pdf_bytes)
    print(f"  [pdf] {path.name} ({len(DOCUMENTS)} documents, multi-page)")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating test documents in {OUTPUT_DIR}/\n")

    print("Text files:")
    txt_paths = create_text_files()

    print("\nPDF files:")
    pdf_paths = create_pdf_files()

    print("\nMulti-page PDF:")
    create_multipage_pdf()

    total = len(txt_paths) + len(pdf_paths) + 1
    print(f"\nDone! Generated {total} files in {OUTPUT_DIR}/")
    print("\nPII coverage per document:")
    print(
        "  kuendigungsschreiben : PERSON, DE_DATE, DE_ADDRESS, DE_IBAN, DE_TAX_ID, DE_PHONE"
    )
    print("  lebenslauf           : PERSON, DE_DATE, DE_ADDRESS, DE_PHONE, DE_ID_CARD")
    print("  handelsregister      : PERSON, DE_DATE, DE_ADDRESS, DE_HANDELSREGISTER")
    print(
        "  rechnung             : PERSON, DE_DATE, DE_ADDRESS, DE_IBAN, DE_TAX_ID, DE_PHONE"
    )
    print("  mixed_edge_cases     : ALL TYPES (dense, overlapping)")


if __name__ == "__main__":
    main()
