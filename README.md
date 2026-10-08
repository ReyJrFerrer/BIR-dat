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

## Deploy to Vercel

The `src/index.py` entry point exposes the FastAPI app to Vercel. Import this repository at [Vercel New Project](https://vercel.com/new), use the repository root as the Root Directory, and deploy a preview first. Vercel reads production dependencies from `pyproject.toml`; no build command or storage service is needed. Check the preview by importing a workbook, editing a field, reloading, and downloading the PDF and DAT before promoting it to production.

In Vercel, each browser tab keeps its review in `sessionStorage`. The browser sends that review to FastAPI when rendering a page, saving a change, or generating a download; the server does not retain it between requests. Closing the tab ends the review, so finish and download the DAT/PDF while it is open. The app has no login; anyone with the URL can use it, but one visitor cannot access another visitor's browser session. Uploaded data is processed by the hosted function and is sent to Vercel on each request.

Vercel Functions limit request bodies to 4.5 MB, so the hosted upload form accepts workbooks up to 4 MB, including room for multipart form data. The local app still accepts 10 MB. A parsed review above 2 MB cannot fit in this browser-session flow and returns an error. See [Vercel's FastAPI guide](https://vercel.com/docs/frameworks/backend/fastapi) and [function limits](https://vercel.com/docs/functions/limitations).

## Workflows

- **SRV / Maria:** reproduces the supplied 612-byte DAT and associates the genuine reference log with its exact hash.
- **Kalamansi:** imports all 11 employees and prioritizes missing employer identifiers and Liza's TIN. Missing identifiers are not filled with invented values.
- **Upload:** recognizes the required 46 headers wherever their columns/rows are moved within the supported XLSX table layout.

Correct only the fields highlighted as errors. Existing values and automatic preparation are retained separately from user corrections. Other source fields are in expandable employee sections. Unknown optional review answers can stay unknown.

Automatic preparation handles identifiers, supported codes, previous-employer compensation, collection/refund differences, missing computed totals, names and ordering. Source tax/benefit categories are preserved. See [the mapping policy](docs/mapping-policy.md) for all rules and evidence limits.

Export names replace Ñ/ñ with N and remove apostrophes, while retaining the original spellings in the workbook and audit. Adjusted spellings appear in the review and PDF. Other unsupported name characters block download until corrected. Employee order follows the export spellings.

When complete, download the **DAT for validation**, its **reconciled PDF**, and the JSON review record. The DAT is a candidate for testing, not proof of BIR approval or submission. The PDF uses the same financial snapshot and sequence as the DAT. Genuine external validation evidence is attached to a particular output hash; any changed DAT loses its association with previous evidence.

The PDF follows `res/Test-1.pdf`: landscape legal pages, embedded Courier New,
stacked BIR column headings, two-line employee entries, page totals, and a
separate grand-total sheet. Full names wrap when needed; original spellings
and employee IDs are available in PDF note annotations. Draft exports retain
a draft label on every sheet and show missing values explicitly.

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

The converter core is independent of FastAPI. Modules cover workbook recognition, typed value objects, candidate policy, normalization/validation, byte serialization, PDF generation, correction/evidence auditing, web presentation and CLI. Financial arithmetic uses Decimal. Local runs process data on the local machine; Vercel deployments process requests in Vercel Functions. No runtime AI service or database is required.
