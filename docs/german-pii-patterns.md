# German PII Detection Patterns

## Overview

This document describes the custom German PII recognizers, their regex patterns, validation logic, and confidence scoring rationale. All recognizers extend Presidio's `PatternRecognizer` and support context-based score boosting.

## Recognizers

### DE_IBAN — German IBAN

**Pattern**: `DE\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}`

**Validation**: ISO 7064 Mod 97-10 checksum (same algorithm used by banks).

**Context words**: IBAN, Konto, Kontonummer, Bankverbindung, Überweisen, Überweisung

**Base score**: 0.5 → boosted to ~0.85 with context, 1.0 with context + valid checksum.

**Examples**:
- `DE89 3704 0044 0532 0130 00` (with spaces)
- `DE89370400440532013000` (without spaces)
- `DE02120300000000202051`

### DE_TAX_ID — Steuernummer and Steuer-ID

**Two patterns**:

1. **Steuer-ID** (Steuerliche Identifikationsnummer): `[1-9]\d{10}`
   - Exactly 11 digits, no leading zero
   - Validation: In the first 10 digits, exactly one digit appears 2-3 times, all others appear at most once
   - Base score: 0.3 (11-digit numbers are common)

2. **Steuernummer**: `\d{2,3}/\d{3}/\d{4,5}`
   - Regional format varies by Bundesland
   - Base score: 0.4

**Context words**: Steuer-ID, Steueridentifikationsnummer, Steuernummer, St.-Nr., Finanzamt

**Examples**:
- Steuer-ID: `12345679811`
- Steuernummer: `93/815/08152` (2-digit Finanzamt)
- Steuernummer: `181/815/08155` (3-digit Finanzamt)

### DE_PHONE — German Phone Numbers

**Three patterns**:

1. **International**: `+49\s?\(?\d{2,4}\)?\s?\d{3,8}[\s-]?\d{0,5}` (score: 0.5)
2. **Domestic**: `0\d{2,4}[\s/-]?\d{3,8}[\s/-]?\d{0,5}` (score: 0.3)
3. **Mobile**: `(?:\+49\s?|0)1[567]\d[\s/-]?\d{3,4}[\s/-]?\d{3,4}` (score: 0.6)

**Context words**: Tel, Telefon, Mobil, Handy, Fax, Rufnummer, Durchwahl, Erreichbar

**Examples**:
- `+49 30 12345678` (Berlin, international)
- `030 12345678` (Berlin, domestic)
- `+49 170 1234567` (mobile, international)
- `0170-1234567` (mobile, domestic)
- `089/12345678` (Munich, with slash)

### DE_ID_CARD — Personalausweisnummer

**Pattern**: `[CFGHJKLMNPRTVWXYZ][CFGHJKLMNPRTVWXYZ0-9]{8}\d`

**Restricted character set**: Only letters C, F, G, H, J, K, L, M, N, P, R, T, V, W, X, Y, Z plus digits 0-9. Letters B, D, I, O, Q, S, U are excluded to avoid visual ambiguity (B/8, D/0, I/1, O/0, Q/0, S/5, U/V).

**Validation**: Check digit using weights 7, 3, 1 repeating. Letters are converted to their ordinal values (A=10, B=11, ..., Z=35).

**Context words**: Personalausweis, Ausweisnummer, Ausweis-Nr., Identitätskarte, Perso

**Base score**: 0.3 (pattern is relatively specific but alphanumeric strings are common)

### DE_HANDELSREGISTER — Commercial Register

**Pattern**: `HR[AB]\s?\d{3,6}\s?[A-Z]?`

- HRA: Partnership companies (OHG, KG)
- HRB: Capital companies (GmbH, AG)

**Context words**: Handelsregister, Registergericht, Amtsgericht, Eingetragen

**Base score**: 0.5

**Examples**:
- `HRB 12345`
- `HRA 98765`
- `HRB 86786 B` (with suffix)

### DE_ADDRESS — German Addresses

**Two patterns**:

1. **PLZ**: `(?:0[1-9]|[1-9]\d)\d{3}` — 5-digit postal code (01000-99999, excluding 00xxx)
   - Base score: 0.2 (5-digit numbers are very common)

2. **Street**: `[A-ZÄÖÜ][a-zäöüß]+(?:straße|str\.|weg|allee|platz|ring|gasse|damm|ufer|chaussee|berg|steig|pfad)\s+\d{1,4}\s?[a-zA-Z]?`
   - Base score: 0.6 (street pattern is quite specific)

**Context words**: Adresse, Anschrift, Wohnhaft, Wohnort, PLZ, Hausnummer

**Examples**:
- `10115` (Berlin-Mitte PLZ)
- `Musterstraße 42`
- `Birkenweg 7`
- `Lindenallee 15a`

### DE_DATE — German Dates

**Two patterns**:

1. **Full**: `(?:0[1-9]|[12]\d|3[01])\.(?:0[1-9]|1[0-2])\.\d{4}` (score: 0.3)
2. **Short**: `(?:0[1-9]|[12]\d|3[01])\.(?:0[1-9]|1[0-2])\.\d{2}` (score: 0.2)

**Context words**: geboren, geb., Geburtsdatum, Geburtstag, Eintrittsdatum, Austrittsdatum, Datum

**Score boosting**: Birth-related context words (geboren, geb., Geburtsdatum) provide the strongest boost, as birth dates are highly sensitive PII.

**Examples**:
- `15.03.1985` (full format)
- `15.03.85` (short format)
- `01.04.2024` (contract date)

## NLP-Based Detection

In addition to regex patterns, spaCy's `de_core_news_lg` model provides NER (Named Entity Recognition) for:

- **PER** → `PERSON`: Personal names
- **LOC** → `LOCATION`: Geographic locations
- **ORG** → `ORGANIZATION`: Company and organization names

These NER entities are detected without explicit patterns, using the model's statistical predictions.

## Scoring

Confidence scores range from 0.0 to 1.0:
- **0.0-0.3**: Low confidence — pattern matched but no supporting context
- **0.3-0.6**: Medium — pattern with some validation or context
- **0.6-0.85**: High — pattern with context boosting and/or checksum validation
- **0.85-1.0**: Very high — multiple signals (pattern + context + validation)

The default threshold is 0.35, balancing recall (catching more PII) against precision (fewer false positives).
