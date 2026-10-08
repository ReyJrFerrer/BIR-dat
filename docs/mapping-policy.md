# Candidate export policy — Option 1

Profile: `1604C-2025-schedule1-candidate-v3`.

The user selected automatic preparation with a DAT for testing in the official validator. This supersedes the earlier policy that blocked every case beyond the single Maria fixture. “Ready for BIR validation” means the supplied records are internally complete and serializable. It does not certify substantive tax classification, official validator acceptance, registered identifiers, refund payment, or filing.

## Rules and evidence

| Area | Implemented rule | Evidence / remaining limit |
| --- | --- | --- |
| Baseline bytes | 4-field H1604C, 49-field D1, 36-field C1, quoted names, fixed two-place decimals, CRLF including final line | Exact supplied Maria DAT and genuine supplied log. Regression matches all 612 bytes and SHA-256. |
| Identifiers | Remove spaces/hyphens, split existing 9-digit TIN and 4-digit branch, retain leading zeroes, reject all-zero TINs | Supplied fixture. No missing identifier or branch is guessed. Registration is not checked. |
| Employment codes | R, C, CP, S, P, AL; separation T, TR, R, D, blank/NA | BIR published Schedule 1 layout lists these statuses and reasons. Unknown codes remain errors. Blank separation does not imply termination. |
| Region | Accept supported source region codes and normalize case | Candidate code list; an accepted code is not evidence of the employee's actual assignment. Target application acceptance remains external. |
| Nationality | Preserve nationality text and validate shape; keep annual tax AR | Nationality does not determine residency or tax treatment. Foreign treatment stays a review note. |
| Previous compensation | Prior non-taxable AJ+AK+AL+AM, taxable AN+AO+AP, gross is their sum; combined taxable = prior taxable + O; adjusted withholding = AQ+P | Published layout supports combined taxable and withholding formulas. Exact D1 fields 37/38/44 for prior employment still require target-app testing. No extra spreadsheet fields are appended. |
| Empty prior block | Serialize zero prior amounts when the workbook records no previous employer; log the interpretation | Source-preserving candidate assumption, not a confirmed employment-history declaration. A populated block is never erased; incomplete populated blocks and contradictory declarations remain errors. |
| Year-end adjustment | Collection=max(P−AS,0), refund=max(AS−P,0); reconcile AQ+P to AR | Published layout contains collection/refund formulas. P is retained as the source final withholding, not verified payment evidence. Inconsistent totals remain errors. Nonzero PERA is unsupported. |
| Low income | Preserve supplied L/O/AR and non-taxable categories; no threshold-based MWE inference | The published layout distinguishes low-income/exempt compensation. Source allocation is retained in this candidate rather than silently reclassifying pay. Official-app field allocation remains a review note. |
| Benefits | Preserve categories E–H and AJ–AM; check components and flag classification/exclusion questions | No automatic payroll recategorization or blanket 90,000 cap. Review notes do not erase a proven arithmetic or classification error. |
| Missing computed totals | If I/L/O is blank and all defined components are present, derive I=E+F+G+H, L=J+K, O=L+M+N | Supplied export's documented relationships; mapping is logged with source cell. Nonblank inconsistent/invalid totals remain errors. Blank compensation categories, AR, P, AS, or PERA are not invented. |
| Diagnostics | Q/R/S/T/U do not feed DAT compensation or tax totals | Blank/invalid diagnostics do not block a candidate. Supplied AR remains authoritative; S is an estimate. An explicitly declared ordinary tax treatment is checked against the 2025 annual table. |
| Names | Preserve source names; for surname, given and middle names normalize canonical Unicode spelling, replace Ñ/ñ with N, remove straight/curly apostrophes, and uppercase without expanding individual Unicode characters. Retain spaces, hyphens and periods; block all other characters, controls, empty required names after normalization, and export names over 50 characters. Keep quoted CSV fields. | User-supplied official validation report rejects the apostrophe in O'BRIEN-SANTOS and Ñ in ÑUNEZ. A–Z, space, hyphen and period form a conservative candidate allowlist based on supplied names, not an exhaustive official character specification. Other characters require a documented correction. Original/export spellings and source cells are retained in automatic mappings; adjusted spellings appear in review, employee details and PDF. Official acceptance still requires revalidation. |
| Encoding | Default Windows-1252; optional UTF-8; strict encoding, no BOM; normalize names before encoding | Accepted candidate names are ASCII and produce the same bytes under either encoding. Encoding changes cannot bypass name-character blockers. Original Unicode spellings remain in the workbook and JSON audit. |
| Order | Deterministic normalized export surname, given name, middle name, employee ID comparison | NUNEZ now sorts before OBRIEN-SANTOS. Review, PDF and DAT share this order and consecutive sequence numbers. Candidate ordinal ordering is not a claim about official collation. |
| Controls | Sum D1 fields 13–23, 26–44, 49 and verify serialized output | Decimal arithmetic; 31 sums plus 5 context fields. Verify record counts, context, sequence and CRLF. No employee is silently omitted. |

## Export states

- **Needs correction:** missing required information, invalid source values, unexplained arithmetic, duplicate records, contradictory declarations, unsupported year/schedule/PERA, unencodable names, or unsupported codes remain.
- **Ready for BIR validation:** every imported record is serializable; unresolved review notes accompany the candidate and remain in JSON. This state never creates a genuine BIR log.
- **Official validation evidence attached:** a genuine supplied reference log or an uploader-attested external log is associated with the exact output hash. Changing DAT bytes makes previous evidence stale. User-attached logs are not independently authenticated.

Optional declarations stay unknown until the user supplies supporting information. They are not automatically changed to confirmed. Declaring an employee an MWE blocks Schedule 1 export; unsupported PERA stays blocked. Declaring an ordinary tax treatment activates its consistency check.

The unchanged Kalamansi workbook still has three blocking source fields: employer TIN, employer branch, and Liza's TIN at V12. It retains all 11 employees and can produce a draft PDF and a review JSON. The application does not synthesize identifiers or exclude Liza.

## References and their limits

- [BIR RMC 160-2022 published Schedule 1/2 layout](https://bir-cdn.bir.gov.ph/local/pdf/RMC%20No.%20160-2022%20AttachmentOriginal.pdf): code lists, compensation groups, and year-end formulas. This older published layout does not independently establish every v7.4 byte/encoding rule.
- [BIR RMC 25-2024 Annex A](https://bir-cdn.bir.gov.ph/BIR/pdf/RMC%20No.%2025-2024%20Annex%20A.pdf): published DAT structure reference. The fetched PDF does not provide extracted text in the browsing tool; no broader acceptance claim is based on its unread extracted contents.
- [BIR RMC 15-2025](https://bir-cdn.bir.gov.ph/BIR/pdf/RMC%20No.%2015-2025.pdf): target v7.4 workflow reference from the supplied specification.
- [BIR RMC 5-2014](https://bir-cdn.bir.gov.ph/BIR/pdf/81938RMC%20No%205-2014.pdf), Question 12(f): historical guidance restricts special characters including ñ. The user's subsequent report for 1604C, 12/31/2025 identifies physical lines 7 and 12 as rejected for an apostrophe and Ñ in the last-name field. These observations establish the targeted substitutions, not a complete official allowlist or acceptance of the regenerated filing. Original names remain unchanged.
- The repository's specification, workbook, DAT, TXT and PDF provide exact source values and baseline evidence. Their hashes remain unchanged.

## Verification

Regression tests use existing supplied employee identities only. Explicit in-memory subsets exercise candidate serialization; they are not demonstration corrections or partial Kalamansi filings. No new synthetic TINs or corrected full-workbook example are generated.

Headless tests validate field positions, original/export name preservation, character blockers, encoding invariance, deterministic export-name order, source financial amounts, controls, PDF values, error gates and hash-bound evidence. The supplied Maria DAT remains byte-for-byte identical. The Windows BIR validation of a full corrected filing remains an external acceptance step.
