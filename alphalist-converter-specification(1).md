# BIR 1604-C Excel-to-DAT and PDF Converter

Version: 1.0 draft for implementation planning  
Prepared: 7 October 2026  
Target fixture: BIR Alphalist Data Entry / Validation v7.4, taxable year 2025

## 1. Objective and scope

Build a program that reads the annual compensation workbook exported from BIRa, validates and maps employee information, and generates:

1. A plaintext 1604-C alphalist DAT compatible with the applicable BIR validation module.
2. A PDF alphalist report similar in organization to the BIR application's printed report, with amounts reconciled to the DAT.
3. A local validation summary identifying missing information, transformations and unresolved issues.

Maggie explicitly permits a spreadsheet program, web application or another presentation. The assessment emphasizes domain understanding and the reasoning behind the solution. The current supplied assignment concerns compensation alphalists, replacing the earlier working assumption of an SLSP converter. The workbook title `1604CF Annualization` must not determine a legacy output format; use the confirmed 1604-C target.

Initial implementation covers Schedule 1 employees and the supplied workbook. Minimum wage earners require explicit identification and a separately verified Schedule 2 implementation; until implemented, report them as unsupported blocking cases. Do not infer minimum-wage status from income below PHP 250,000.

Out of scope: payroll processing, replacing the app's annualization engine, electronic invoicing under RMC 98-2026, individual Form 2316 certificates unless requested, automatic tax filing, and generating BIR encrypted submission packages. The program generates plaintext for official validation; downstream packaging remains with the BIR tools.

## 2. Evidence and its limits

### Supplied artifacts

| Artifact | Role |
| --- | --- |
| `Kalamansi Trading 1604CF Annualization 2025.xlsx` | Input contract: one worksheet, 11 employees, 46 columns, header row 5, employee rows 6–16, totals row 17 |
| `6847855100000123120251604C.DAT` | Verified single-employee serialization fixture from SRV Digital Solutions |
| `6847855100000123120251604C.TXT` | BIR validator report containing `No Errors Encountered` |
| `{9D62F333-B060-4A2C-A3D8-4770EB01D220}.png` | User-provided successful validation dialog |
| `Test.pdf` | Two-page BIR-generated report; visual reference with confirmed amount discrepancies |

The DAT contains one H1604C record, one D1 employee record and one C1 control record. Its SHA-256 is `59892d6a782fb46aa44060ec9ca74db5ae3a3862eb247513908b8bb6a519c788`. The TXT SHA-256 is `acc3b57944f1232a456d77ac8417ae12829636a7b93ad9278b495240818f9505`. Preserve fixtures unchanged in the implementation repository and compare hashes when copying them.

**Validation evidence applies to the supplied DAT, not automatically to the PDF, the whole workbook, or future files.** It is not an eSubmission acknowledgment or evidence that identifiers are registered taxpayers.

### Confirmed PDF discrepancy

The rendered PDF shows `0.00` for present taxable salaries/other compensation and total taxable compensation, while D1 fields 33, 36, 37 and 38 contain `449812.50`. Its report title says employees with previous employers even though this employee has none. The displayed employer branch also differs in formatting from the DAT. The PDF spans two landscape legal pages, with grand totals alone on the second page.

Use this PDF to understand the visual style and grouping, not as the numeric oracle. Do not reproduce wrong zero amounts or hardcode its previous-employer title. Investigate whether another report option produces the correct report before final visual approval. Do not assert an application bug: wrong report selection, stale rendering or another cause remains possible.

### Public references

- [RMC 15-2025: Alphalist v7.4](https://bir-cdn.bir.gov.ph/BIR/pdf/RMC%20No.%2015-2025.pdf)
- [RMC 25-2024 Annex A: published 1604-C structure](https://bir-cdn.bir.gov.ph/BIR/pdf/RMC%20No.%2025-2024%20Annex%20A.pdf)
- [RMC 15-2025 Annex B: naming conventions](https://bir-cdn.bir.gov.ph/BIR/pdf/RMC%20No.%2015-2025%20Annex%20B.pdf)
- [BIR data-entry job aid, earlier v7.0 workflow](https://bir-cdn.bir.gov.ph/local/pdf/RMC%20No.%207-2021%20Annex%20C%20-%20DE_optimized.pdf)
- [BIR validation job aid](https://bir-cdn.bir.gov.ph/local/pdf/RMC%20No.%207-2021%20Annex%20C%20-%20Val_optimized.pdf)
- [BIR Form 1700: annual tax table effective 2023 onward](https://bir-cdn.bir.gov.ph/local/pdf/1700%20Jan%202018%20ENCS%20v6.pdf)

These sources establish the versioned workflow and provide specifications to cross-check. This document's exact bytes and sample amounts come from the user's files. Before claiming general v7.4 support, reconcile the published structure with applicable intervening updates and the installed validator. Do not treat an older annex or one passing sample as a complete specification for all schedules and edge cases.

## 3. Product workflow

1. Select the XLSX input.
2. Detect its worksheet and header; show reporting year and employee count.
3. Supply withholding-agent name, nine-digit TIN, branch code and reporting period. Add report metadata only if the chosen layout needs it.
4. Display imported records, derived values, warnings and blocking errors with employee ID and source cell.
5. Resolve missing metadata or supply explicit corrections, retaining original values and an audit record.
6. Review compensation and withholding totals.
7. Generate DAT and PDF from the same validated snapshot.
8. Run the generated DAT in the official Windows validation module and retain its actual result as evidence.

Allow draft report previews with a visible `DRAFT — unresolved data` label. Block final DAT and final PDF export if any required row remains invalid. Do not silently omit employees or export a partial filing. Do not claim official validation merely because internal checks pass.

Keep SRV Digital Solutions as a test fixture, separate from Kalamansi Trading. Its TIN `684785510` and branch `0000` must never silently become the default employer identity for an unrelated workbook. They are user-supplied synthetic test values, not a reserved test range.

## 4. Input contract and normalization

- Accept XLSX; CSV is optional future scope. Parse values, not a screenshot or a printed representation.
- Match the expected worksheet and required header labels; do not permanently depend on row 5 or fixed column positions. The column letters below identify this version of the source export.
- Read each employee row once. Exclude introductory notes, blank rows and the `TOTAL` row. Reject ambiguous duplicate headers and unsupported workbook layouts with actionable messages.
- The heading refers to 202 payslips, but the file contains 11 annual employee records, not 202 transactions. Never multiply annual amounts by pay frequency.
- Treat amounts as decimal values or integer centavos. Round only at documented calculation boundaries. Do not use binary floating-point for financial arithmetic.
- Preserve zero separately from missing. An absent previous employer may yield zero monetary fields under an explicit no-previous-employer state; missing fields in an existing previous-employer block are errors.
- Use W/X/Y for surname/given/middle names. B is a display name, not a reliable parsing source. A missing middle name is distinct from a missing surname.
- Normalize TIN separators, then split the employee's 9-digit TIN and 4-digit branch for this pinned fixture profile. Preserve leading zeros. Never truncate or guess extra digits.
- Convert dates to valid calendar dates. Accept the export's ISO date strings and supported Excel date cells; write MM/DD/YYYY in DAT. Use reporting year 2025 rather than the workbook generation date in 2026.
- Require employment dates within the relevant reporting period or an explicit documented annualization policy. A December 31 reporting cutoff does not prove that employment terminated.
- Preserve source names including Ñ and apostrophes. Until the validator's supported encoding and escaping rules are verified, flag unsupported characters rather than silently transliterating or deleting them.
- Keep originals, normalized values and source coordinates. User corrections are explicit overrides; do not rewrite the source workbook.

## 5. Canonical data model and architecture

Use a reusable conversion core with a thin interface. Recommended initial delivery: a small local web application plus a command-line entry point for repeatable tests. Language remains an implementation choice; Python is a practical option. This specification does not require a framework, cloud service, database or account system.

Core components:

| Component | Responsibility |
| --- | --- |
| Workbook reader | Recognize export schema; retain original rows and cell references |
| Normalizer | Parse identifiers, names, dates, decimals and controlled values |
| Domain mapper | Map present/prior compensation and calculate derived values |
| Validator | Return structured errors/warnings; reconcile source and output |
| DAT writer | Serialize a pinned schema and filename deterministically |
| PDF renderer | Render the exact same validated records and totals |
| Review interface | Collect metadata and corrections; explain errors; download outputs |

Model a FilingContext, EmployeeAnnualRecord, EmployerCompensation, WithholdingAdjustment and ValidationIssue. A ValidationIssue has severity, code, employee ID, source cell, field, observed value and suggested correction. Store an explicit profile/version identifier and source-file hash with each conversion result. Validation and output generation must not mutate source values.

The same validated snapshot feeds both writers; the PDF must not independently recalculate payroll amounts. Files can be processed locally without persistent server storage. No AI service is required at runtime; financial transformations must be deterministic and inspectable.

## 6. Financial mappings and checks

### Source relationships confirmed across the 11 rows

```text
present.nonTaxableTotal = E + F + G + H = I
present.netBasic = J + K = L
present.taxableTotal = L + M + N = O
present.gross = I + O
previous.nonTaxableTotal = AJ + AK + AL + AM
previous.taxableTotal = AN + AO + AP
previous.gross = previous.nonTaxableTotal + previous.taxableTotal
combined.taxable = previous.taxableTotal + present.taxableTotal
```

K is negative in this export; G is the same contribution magnitude under non-taxable compensation. Do not subtract G again from L. Confirm row arithmetic to the cent; do not repair disagreements silently. Gross here is a reporting derivation from the supplied categories, not an instruction to recalculate historical payroll.

Use AR (`Tax Due (Jan–Dec)`) as the supplied annual-tax field and validate it against the applicable tax treatment. S (`Est. Annual Tax`) is a diagnostic estimate, not a substitute for AR. R/T/U are diagnostic values, not extra compensation to add to O. Q is a remaining-benefit-exclusion diagnostic, not compensation or withholding.

For the non-PERA cases in this workbook, the proposed year-end mapping is:

```text
previousWithheld = AQ
presentBeforeAdjustment = AS
presentFinalWithheld = P
delta = P - AS
DecemberAdditionalWithholding = max(delta, 0)
Refund = max(-delta, 0)
combinedFinalWithheld = AQ + P
```

The Maria fixture confirms the positive-delta mapping. Verify the negative-delta and previous-employer mappings in the official app before marking those cases supported. A calculated refund difference does not independently prove that a refund was actually paid. A nonzero AT/PERA case requires a separate fixture and confirmed rules; do not invent its interaction with actual withholding.

Specific regression cases:

- Maria: gross 532,000.00; non-taxable 82,187.50; taxable 449,812.50; tax due 32,462.50; Jan–Nov withheld 29,000.00; December additional 3,462.50.
- Carlo: current taxable 316,800.00 plus prior taxable 257,000.00 gives 573,800.00. AR is 57,260.00; S is only 10,020.00. Prior withheld 1,050.00 plus current final 56,210.00 reconciles to AR. Proposed December additional is 11,210.00.
- Pedro: current final 196,175.00 minus Jan–Nov 200,000.00 gives a proposed refund of 3,825.00. Do not serialize this as a negative December collection without confirming the official behavior.

Review the export's statement that both E and H consume the PHP 90,000 benefits exclusion. The meaning of H is app-specific and must be confirmed before implementing automatic reclassification. Do not apply a blanket cap to every non-taxable category. Likewise, validate the current/prior annual exclusion together where applicable rather than treating two employers as two independent annual allowances.

## 7. DAT serialization profile

### Confirmed byte-level rules from the supplied fixture

- Plain comma-delimited text; no column-heading row.
- H1604C header: 4 fields.
- D1 detail: exactly 49 fields per employee.
- C1 control: exactly 36 fields.
- CRLF line endings, including after the last record.
- The supplied fixture is 612 bytes, ASCII-compatible and has no BOM. Its all-ASCII content cannot establish the application's encoding for non-ASCII names.
- Dates are MM/DD/YYYY. Amounts have two decimal places and no thousands separator or currency symbol.
- Name fields 9–11 are double-quoted in the reference; nationality, codes and dates are unquoted. Preserve this rule for fixture reproduction. Verify embedded quote/comma behavior with an additional generated example.
- Sequence numbers are unpadded (`1` in the fixture). Assign consecutive sequence numbers after the verified alphabetical ordering policy; duplicate names need a deterministic tie-breaker.
- Filename pattern observed: `<TIN9><Branch4><MMDDYYYY>1604C.DAT`.
- Example: `6847855100000123120251604C.DAT`.

Retain raw reference bytes. A reproduction test for the Maria fixture must match all 612 bytes and the SHA-256 above. Do not generalize a format change from a single example; pin a schema profile and test it in the actual validator.

### Header

```text
H1604C,{employerTIN},{employerBranch},{periodEnd}
```

### D1 mapping, 1-based field positions

This is the observed Schedule 1 order. Fields with unresolved broader behavior are marked in the notes; their fixture values are known.

| Position | Meaning | Source or rule |
| --- | --- | --- |
| 1 | Record type | `D1` |
| 2 | Form | `1604C` |
| 3 | Employer TIN | Filing context |
| 4 | Employer branch | Filing context |
| 5 | Period end | `12/31/2025` for this filing |
| 6 | Sequence | Generated after ordering |
| 7 | Employee TIN | V, normalized first 9 digits |
| 8 | Employee branch | V, explicit branch portion |
| 9 | Surname | W; quoted |
| 10 | Given name | X; quoted |
| 11 | Middle name | Y; quoted |
| 12 | Region | AC; verify valid codes |
| 13 | Prior gross compensation | Derived prior gross |
| 14 | Prior non-taxable basic/statutory wage | Not separately supplied; zero only after non-MWE/classification confirmation |
| 15 | Prior non-taxable benefits | AJ |
| 16 | Prior de minimis | AK |
| 17 | Prior contributions/union dues | AL |
| 18 | Prior non-taxable other salaries | AM |
| 19 | Prior total non-taxable | AJ + AK + AL + AM, subject to classification |
| 20 | Prior taxable basic salary | AN |
| 21 | Prior taxable benefits | AO |
| 22 | Prior taxable other compensation | AP |
| 23 | Prior taxable total | AN + AO + AP |
| 24 | Present employment from | C |
| 25 | Present employment to | D |
| 26 | Present gross compensation | I + O |
| 27 | Present non-taxable basic salary | Not separately supplied; classification must be confirmed |
| 28 | Present non-taxable benefits | E |
| 29 | Present de minimis | F |
| 30 | Present contributions/union dues | G, positive |
| 31 | Present non-taxable other salaries | H |
| 32 | Present non-taxable total | I, cross-check component sum |
| 33 | Present taxable basic salary | L, not J |
| 34 | Present taxable benefits | M |
| 35 | Present taxable other compensation | N |
| 36 | Present taxable total | O |
| 37 | Combined amount in schema's GROSS_COMP_INCOME position | Fixture contains taxable 449812.50, NOT gross 532000.00; proposed prior + present taxable; confirm prior-employer case |
| 38 | Net taxable compensation | Fixture 449812.50; proposed combined taxable subject to applicable adjustments |
| 39 | Annual tax due | AR; cross-check applicable treatment |
| 40 | Previous employer withholding | AQ or explicit no-prior zero |
| 41 | Present withholding before year-end adjustment | AS, NOT P |
| 42 | December additional withholding | Proposed max(P − AS, 0); Maria confirmed |
| 43 | Refund | Proposed max(AS − P, 0); refund fixture required |
| 44 | Actual adjusted withholding | Maria 32462.50; proposed AQ + P for no-PERA cases; prior-employer fixture required |
| 45 | Nationality | Z; preserve verified allowed representation |
| 46 | Current employment status | AA; validate against official list |
| 47 | Separation reason | AB; observed absent-reason representation `NA` |
| 48 | Substituted filing | AD: Yes → Y, No → N, with eligibility review |
| 49 | PERA credit | AT; zero in supplied examples |

AE–AI provide previous-employer identity/status/dates and can support validation and review, but the observed 49-field record has no corresponding direct fields for all of them. Do not append extra fields simply to preserve every spreadsheet column.

The published labels alone can be misleading: field 37 must not be populated with all gross pay simply because its technical name contains GROSS. Use verified application behavior and additional examples to resolve semantics.

### C1 controls

First five fields: `C1,1604C,{employerTIN},{employerBranch},{periodEnd}`.

For all emitted D1 records, sum the following fields in this exact order:

```text
D1[13..23], D1[26..44], D1[49]
```

These 31 numeric totals plus the first five fields produce 36 fields. Sum the validated decimal values, not formatted strings. Do not sum sequence numbers, codes or dates. Check each control against a fresh aggregation of serialized detail records.

### Exact Maria reference

The following logical lines must be written using CRLF, including a final CRLF; Markdown itself does not preserve those byte requirements.

```text
H1604C,684785510,0000,12/31/2025
D1,1604C,684785510,0000,12/31/2025,1,901234567,0000,"REYES","MARIA","SANTOS",NCR,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,01/01/2025,12/31/2025,532000.00,0.00,40000.00,12000.00,30187.50,0.00,82187.50,449812.50,0.00,0.00,449812.50,449812.50,449812.50,32462.50,0.00,29000.00,3462.50,0.00,32462.50,FILIPINO,R,NA,Y,0.00
C1,1604C,684785510,0000,12/31/2025,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,532000.00,0.00,40000.00,12000.00,30187.50,0.00,82187.50,449812.50,0.00,0.00,449812.50,449812.50,449812.50,32462.50,0.00,29000.00,3462.50,0.00,32462.50,0.00
```

## 8. PDF requirements

- Default to landscape legal: 1008 × 612 points (14 × 8.5 inches), as observed.
- Use a compact monochrome tabular style with readable text, grouped headings and report date/year.
- Show employer name and TIN/branch, sequence, employee TIN and name, previous/current compensation groups, tax due, previous/current pre-adjustment withholding, PERA, December collection, refund, adjusted withholding and substituted-filing status.
- Include enough compensation detail to reconcile totals, including taxable basic salary and de minimis. If an older BIR printout collapses categories, document the aggregation instead of omitting amounts.
- Choose an accurate Schedule 1 title. Only use a previous-employer-specific title if the report is intentionally filtered to that population.
- All financial values must come from the same validated snapshot as the DAT. Correctly display Maria's 449,812.50 taxable amount; do not copy the reference PDF's zero.
- Repeat necessary column headings and employer/year context on continuation pages. Prevent clipped values, overlapping columns and detached employee rows. Wrap long names without silently truncating them.
- Print page subtotals, a grand total and an end-of-report marker. Keep grand totals on the last populated page where space permits; a second page solely because the reference has one is not required.
- Distinguish absent prior-employer information from zero-valued prior compensation in the model, even if the printed monetary cells show 0.00.
- Inspect rendered output at normal reading scale and compare report values to parsed DAT details and controls.
- The PDF is the converter's generated report, not a forged BIR validation certificate. Do not generate a `No Errors Encountered` BIR log; attach only genuine externally produced logs.

## 9. Validation requirements

Blocking errors include missing employer identifiers; Liza Garcia's missing V12 TIN; invalid date or code; duplicate employee records; unsupported schedule; unexplained arithmetic inconsistency; unsupported character conversion; and required fields missing from a populated prior-employer record.

Warnings/review issues include source estimate versus final tax differences, possible year-end refunds, uncertain benefit classification, unexpectedly blank middle names, and discrepancies in the supplied PDF. Escalate a review issue to a blocker when it makes a required output value indeterminate.

Map substituted filing only after reviewing applicable eligibility. `Yes` in the export is input evidence, not proof of eligibility. Nationality alone does not establish tax residency or the applicability of a special tax treatment. Preserve the supplied annual tax and flag unresolved classification rather than assuming every foreign employee has the same treatment.

Expose distinct states: `Imported`, `Needs correction`, `Passed internal checks`, and `Official validation evidence attached`. Associate external evidence with the exact output hash so a changed file cannot retain a stale validation badge.

Reconcile the unchanged workbook's source controls:

| Measure | Expected source value |
| --- | ---: |
| Employee rows | 11 |
| Present non-taxable total | 623085.66 |
| Present taxable total | 4100331.50 |
| Present final withholding | 422807.50 |
| Previous withholding | 1050.00 |
| Annual tax due, AR sum | 423857.50 |
| Present Jan–Nov withholding, AS sum | 400000.00 |

These are source reconciliation controls, not a guarantee that all output categories remain unchanged after justified tax-classification review. Any authorized adjustment must be explained and reconciled to the original totals.

## 10. Acceptance tests

| ID | Test | Required result |
| --- | --- | --- |
| AT01 | Recreate Maria under SRV context | DAT matches the supplied 612 bytes and SHA-256 exactly |
| AT02 | Parse reference DAT | Record field counts 4 / 49 / 36; no omitted trailing zero field |
| AT03 | Recompute C1 | Every numeric control matches detail aggregation |
| AT04 | Original Kalamansi workbook | Exactly 11 employees detected; employer metadata and missing V12 flagged; final export blocked |
| AT05 | Explicit corrected synthetic fixture | All employees accounted for; original workbook retained; changes recorded |
| AT06 | Prior-employer case | Carlo includes 257000.00 prior taxable and 1050.00 prior withheld; official-app comparison resolves fields 37/38/44 |
| AT07 | Refund case | Pedro's 3825.00 difference mapped to the verified refund field; no incorrect negative collection |
| AT08 | Zero-tax regular employee | Correct Schedule 1 treatment established independently of MWE status and threshold classification |
| AT09 | Names | Ñ, apostrophe, hyphen, suffix and blank middle name follow verified validator rules without hidden data loss |
| AT10 | Benefit threshold / PERA | Additional fixtures verify behavior; unsupported cases fail explicitly until covered |
| AT11 | Invalid inputs | Bad TIN lengths, conflicting duplicates, invalid dates, unknown codes and missing required columns give specific errors |
| AT12 | Layout variation | Supported header/row movement does not ingest totals as an employee or misalign columns |
| AT13 | PDF reconciliation | Maria taxable 449812.50, tax due 32462.50 and adjusted withholding 32462.50; all totals equal model and DAT |
| AT14 | Multi-page PDF | Long names and at least two pages of repeated test records remain readable; page/grand totals are correct |
| AT15 | Determinism | Identical input, context, overrides and profile produce identical DAT bytes |
| AT16 | Official validator | Generated multi-employee DAT passes the target BIR validator; save version, hash and actual log |

Passing AT01 validates the serializer's baseline only. Completion requires the broader cases, corrected input and full-file validation. A successful BIR validation log does not establish tax-return submission or every substantive tax classification.

## 11. Implementation order and deliverables

1. Preserve reference fixtures and reproduce Maria exactly with a pure serializer.
2. Implement workbook ingestion, normalization and source reconciliation.
3. Add explicit employer context and employee overrides; surface known missing data.
4. Verify previous-employer, refund, low-income and special-character cases against the official application. Resolve profile rules before broad support claims.
5. Generate the PDF from the shared validated snapshot and compare both outputs.
6. Add a minimal review/download interface and clear run instructions.
7. Demonstrate the original invalid-input case, an explicitly corrected synthetic case and successful official validation.

Deliver source code, setup instructions, schema/mapping documentation, tests, unchanged reference fixtures, generated sample DAT/PDF, a correction/assumption record, and genuine validator evidence. Keep the implementation focused; a database or cloud deployment is unnecessary for this assignment unless chosen for a concrete reason.

## 12. Open decisions and data requests

### Information only Maggie or the source-data owner can confirm

- Synthetic employer TIN/branch for Kalamansi and the missing employee TIN, or explicit permission to use documented synthetic replacements for the demonstration.
- Whether any employee is intended to be an MWE and the meaning of the app's non-taxable basic/other compensation categories.
- Whether P is finalized actual present-employer withholding, including processed refunds, and whether AR is the authoritative annualized tax.
- Expected PDF scope: annual alphalist only, a particular report view, or individual 2316 certificates as well.
- Submission deadline and any evaluation-environment constraints.

### Research / implementation responsibilities

- Verify the installed 7.4 patch level and applicable file specifications, code lists, field widths, sort order and character rules.
- Resolve non-taxable basic-salary treatment for lower-income employees and field 37/38 semantics using additional official-app examples.
- Confirm refund and nonzero PERA behavior without relying on the questionable PDF formulas.
- Identify the correct BIR report option and investigate the supplied PDF discrepancy.

These decisions do not block building the Maria baseline, importer, validation UI or renderer structure. They do block claiming a complete, compliant conversion of all supplied employees.
