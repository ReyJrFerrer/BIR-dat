# Alphalist review and conversion

A local Python web application for reviewing BIRa annualization exports and preparing Schedule 1 Form 1604-C candidates for the official BIR validator.

## Run

From this repository:

```sh
source .venv/bin/activate
alphalist serve
```

Open http://127.0.0.1:8000. Stop with Ctrl+C. After a code change, restart the server. Reviews are kept in memory and expire after two hours of inactivity or a restart; download the JSON review record before restarting if you need to retain your correction history.

For a fresh installation (Python 3.12 or newer):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/alphalist serve
```

The [development dependency snapshot](requirements-dev.lock) records the tested macOS ARM64 / Python 3.14 environment. Other platforms should install the declared dependencies in `pyproject.toml`; the snapshot includes platform-specific development tools.

## Workflows

- **SRV / Maria:** reproduces the supplied 612-byte DAT and associates the genuine reference log with its exact hash.
- **Kalamansi:** imports all 11 employees and prioritizes missing employer identifiers and Liza's TIN. Missing identifiers are not filled with invented values.
- **Upload:** recognizes the required 46 headers wherever their columns/rows are moved within the supported XLSX table layout.

Correct only the fields highlighted as errors. Existing values and automatic preparation are retained separately from user corrections. Other source fields are in expandable employee sections. Unknown optional review answers can stay unknown.

Automatic preparation handles identifiers, supported codes, previous-employer compensation, collection/refund differences, missing computed totals, names and ordering. Source tax/benefit categories are preserved. See [the mapping policy](docs/mapping-policy.md) for all rules and evidence limits.

Export names replace Ñ/ñ with N and remove apostrophes, while retaining the original spellings in the workbook and audit. Adjusted spellings appear in the review and PDF. Other unsupported name characters block download until corrected. Employee order follows the export spellings.

When complete, download the **DAT for validation**, its **reconciled PDF**, and the JSON review record. The DAT is a candidate for testing, not proof of BIR approval or submission. The PDF uses the same financial snapshot and sequence as the DAT. Genuine external validation evidence is attached to a particular output hash; any changed DAT loses its association with previous evidence.

Windows-1252 is the default candidate encoding; UTF-8 is available in Employer details. Supported export names are ASCII under either encoding. Revalidate regenerated files in the installed BIR validator. Unsupported MWE/Schedule 2 and nonzero PERA remain blockers.

## CLI

Output directories must be new so existing results are not overwritten:

```sh
alphalist review --reference validated --output outputs/srv-reference
alphalist review --reference workbook --output outputs/kalamansi-review
alphalist review --workbook 'data/Kalamansi Trading 1604CF Annualization 2025.xlsx' --output outputs/import-review
```

The original incomplete workbook produces JSON and a marked draft PDF, without a partial DAT.

## Checks

```sh
.venv/bin/pytest -q
.venv/bin/ruff check src tests
.venv/bin/mypy src
```

The converter core is independent of FastAPI. Modules cover workbook recognition, typed value objects, candidate policy, normalization/validation, byte serialization, PDF generation, correction/evidence auditing, web presentation and CLI. Financial arithmetic uses Decimal. Processing stays on the local machine; no runtime AI service or database is required.
