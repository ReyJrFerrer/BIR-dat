# Python alphalist converter implementation plan

## Current policy amendment: Option 1 (8 October 2026)

The user selected automatic preparation and a DAT for official validation. The implemented candidate profile supersedes the original requirement to block every unverified broader case. Required data errors and unsupported schedules/PERA remain blockers. Source-preserving prior-employer/refund mappings, code support, ordering and lossless character encoding run automatically; unknown classifications and target-validator uncertainties accompany the candidate as review notes. No declaration is silently marked confirmed, no payroll category is silently reclassified, and no missing TIN is fabricated. The original full Kalamansi filing still has three identifier blockers.

See [mapping-policy.md](docs/mapping-policy.md) for the implemented rules and evidence limits, and [README.md](README.md) for run/test commands. Earlier planning sections below describe the initial strict profile and should be read subject to this amendment.

## Intended outcome

A local browser application that imports the supplied annualization XLSX, explains validation issues, accepts explicit employer metadata and audited employee corrections, and generates a Schedule 1 Form 1604-C DAT, reconciled PDF, and validation summary. A reusable Python core and CLI share the same conversion pipeline. The source workbook and BIR reference files remain unchanged.

Final exports require a complete validated filing. Draft PDF previews are visibly marked. Internal validation and genuine official BIR validation are separate states; external evidence belongs to the exact DAT hash.

## Artifact review performed

- Workbook: one sheet, `1604CF Annualization`; 46 columns; headers on row 5; 11 employee rows on rows 6–16; TOTAL on row 17. Reporting year is 2025, although generation occurred in 2026.
- Recomputed source totals: present non-taxable 623085.66; present taxable 4100331.50; present final withholding 422807.50; previous withholding 1050.00; annual tax due 423857.50; present Jan–Nov withholding 400000.00.
- DAT: 612 bytes, three CRLF-terminated records, field counts 4/49/36. SHA-256 matches the specification: `59892d6a782fb46aa44060ec9ca74db5ae3a3862eb247513908b8bb6a519c788`.
- TXT: contains `No Errors Encountered`; SHA-256 matches `acc3b57944f1232a456d77ac8417ae12829636a7b93ad9278b495240818f9505`. This validates the supplied single-employee fixture only.
- PDF: inspected text and page geometry; two landscape legal pages (1008 × 612 points), previous-employer-specific title, grand totals on page 2, and extracted taxable amounts inconsistent with the DAT. Visual rendering inspection remains part of PDF implementation acceptance.
- The validation-dialog PNG mentioned in the specification is not present under `res/`.

## Proposed engineering approach

Use FastAPI with Jinja2 templates and a small amount of browser JavaScript; openpyxl for XLSX; ReportLab for PDF; Python Decimal for money; pytest, Ruff, and type checking for verification. Declare dependencies and supported Python versions in pyproject.toml and retain a reproducible dependency lock. Confirm dependency compatibility against the repository environment before selecting final pins.

Use a src/alphalist package with separate domain, workbook, normalization, validation, profiles, DAT, PDF, web, and CLI modules. Typed models include FilingContext, EmployeeAnnualRecord, EmployerCompensation, WithholdingAdjustment, ValidationIssue, and an immutable validated filing snapshot. Writers consume the same snapshot without recalculating payroll independently.

Bind locally by default. Bound upload size and XLSX expanded size, validate file structure, isolate browser sessions, expire temporary work, escape displayed source values, and avoid employee data in logs. No database or external AI service is needed. Corrections retain source coordinates, original values, reasons, and output/source hashes; downloading an audit record allows work to be retained without persistent server storage.

## Implementation sequence and acceptance gates

1. **Project foundation.** Finish packaging, locked dependencies, application entry points, configuration, test structure, lint/type settings, and setup documentation. The repository `.venv` already exists with openpyxl and pypdf installed for this inspection; application dependencies are not yet installed.
2. **Pinned reference serializer.** Preserve raw fixtures in place. Implement typed D1/C1 mappings, explicit quoting, fixed decimal formatting, filename generation, and CRLF endings. Gate: reproduce Maria byte-for-byte and verify all control sums (AT01–03).
3. **Workbook ingestion.** Recognize required headers rather than fixed coordinates; preserve original values and locations; exclude totals and notes; distinguish blanks from zero. Detect missing formula caches instead of inventing calculated values. Gate: 11 records and exact source controls; schema movement and invalid-layout tests (AT04, AT11–12).
4. **Domain mapping and validation.** Map separate name columns, identifiers, dates, previous employment, benefits, and withholding. Preserve supplied AR annual tax, use S diagnostically, and avoid subtracting contributions twice. Structured issues identify employee, cell, reason, and correction. Gate: known missing TIN and employer metadata block final export, with no silently dropped employees.
5. **Resolve versioned BIR rules.** Check official specifications and installed validator version; obtain official-app examples for prior employment, refund, low-income non-MWE treatment, codes, ordering, and character encoding. Confirm fields 37/38/44 and special cases. Keep unresolved required semantics blocked; unsupported MWE/PERA cases fail explicitly (AT06–10). This work can proceed alongside importer/UI development.
6. **Review workflow.** Build upload, filing metadata, issue review, explicit corrections, employee details, reconciliation, and export screens. States: Imported, Needs correction, Passed internal checks, Official validation evidence attached. Keep fixture employer SRV separate from Kalamansi. Gate: original workbook stays unchanged, overrides are auditable, and all 11 records remain accounted for (AT05).
7. **PDF generation.** Render the validated snapshot with accurate title, grouped columns, repeated context, readable names, subtotals, grand totals, and end marker. Provide marked draft previews. Gate: values reconcile with parsed DAT and model; inspect rendered pages, long names, and multipage cases (AT13–14).
8. **Integration and delivery.** Exercise web and CLI flows, deterministic DAT generation, export blocking, correction invalidation of old evidence, and malformed uploads. Run tests, lint, and type checks. Deliver README, profile/mapping notes, correction record, and clearly identified sample outputs (AT15).
9. **Official acceptance.** Run the complete corrected multi-employee DAT in the target Windows BIR validator and retain genuine log, version, and DAT hash (AT16). This depends on access to that application or a user-provided test run; internal checks alone cannot satisfy it.

## Confirmed constraints from the data recipient

The user cannot supply missing TINs, authorize synthetic identifiers, or confirm source-data classifications and withholding semantics. Treat the supplied artifacts as the complete available evidence. Do not request these answers again as a prerequisite for building the application, fabricate identifiers, reuse SRV's identity for Kalamansi, or infer classifications from income or nationality.

The original workbook must produce a complete 11-employee review, source reconciliation, downloadable validation summary, and visibly marked draft PDF. Show missing employer identifiers and V12 as `Not supplied` in the review/report, never as placeholder identifiers in a DAT. Preserve unresolved classifications as unknown and distinguish observed source amounts from proposed derived mappings.

Final DAT and final PDF remain unavailable while required identifiers or output semantics are unresolved. Explain each blocker with its source location and the reason the target format requires resolution. This is a supported incomplete-input workflow, not an application failure. Never silently omit Liza or export a partial filing. A schema-compatible serializer does not make an incomplete filing acceptable to BIR.

Use only the existing SRV/Maria fixture for the verified serializer demonstration, explicitly labeled as a separate reference case. No new synthetic identifiers or corrected synthetic full-workbook sample are authorized. Retain AT05 as a future conditional test requiring legitimate supplied corrections; it is not an acceptance gate for the available-input delivery. The original full-workbook official-validation gate AT16 remains externally blocked and must be reported as unfulfilled, rather than passed or removed.

Research official specifications and obtain additional official-app evidence where possible to resolve format behavior independently. User declarations cannot substitute for verified encoding or field semantics. Complete all implementation and internal checks possible with the available input; document the remaining evidence gaps.

## Outstanding evidence, not questions the user must answer

- Kalamansi employer TIN/branch and Liza Garcia's missing V12 TIN are unavailable. Synthetic replacements are not authorized.
- Explicit MWE classification, source meanings of non-taxable basic/other compensation, and applicable treatment for the foreign-national employee.
- Whether P represents finalized actual withholding including processed refunds, and whether AR is the authoritative annualized tax.
- Confirm annual alphalist PDF scope; individual 2316 certificates are outside the current specification.
- Access to the installed BIR validator and additional official-app fixtures for unresolved cases.

These evidence gaps do not prevent delivery of the serializer, importer, review UI, validation summary, or draft PDF. They prevent claiming a complete officially validated Kalamansi filing. The application must handle that outcome explicitly without requiring the user to provide answers they do not have.
