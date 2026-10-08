"""Review operations and reference evidence, independent of the web framework."""

from dataclasses import asdict
from datetime import UTC, datetime

from .conversion import DECLARATIONS, build_snapshot, effective_declarations
from .dat import digest, serialize
from .domain import (
    LOG_HASH,
    REFERENCE,
    REFERENCE_HASH,
    REFERENCE_LOG,
    WORKBOOK,
    Correction,
    Evidence,
    FilingContext,
    Review,
    SourceWorkbook,
)
from .workbook import HEADERS, read_workbook


def load_reference(kind: str) -> Review:
    source = read_workbook(WORKBOOK.read_bytes(), WORKBOOK.name)
    if kind == "workbook":
        return Review(source)
    if kind != "validated":
        raise ValueError("Unknown reference.")
    reference = REFERENCE.read_bytes()
    log = REFERENCE_LOG.read_bytes()
    if digest(reference) != REFERENCE_HASH or digest(log) != LOG_HASH:
        raise ValueError("Reference fixture hashes do not match the recorded evidence.")
    maria = next(row for row in source.rows if row.values["A"] == "EMP-0007")
    review = Review(
        SourceWorkbook(
            "SRV / Maria reference (source workbook row 6)",
            source.sha256,
            source.sheet,
            [maria],
            FilingContext("SRV DIGITAL SOLUTIONS", "684785510", "0000", "2025"),
        )
    )
    # Fixture-only interpretations; never inherited by another employee/workbook.
    review.declarations[maria.key] = {
        key: "non_mwe" if key == "schedule" else "none" if key == "prior" else "confirmed"
        for key in DECLARATIONS
    }
    if serialize(build_snapshot(review)) != reference:
        raise ValueError("Workbook Maria no longer reproduces the verified reference.")
    review.evidence = Evidence(
        REFERENCE_HASH,
        LOG_HASH,
        "7.4 (supplied evidence; patch unspecified)",
        log.decode("ascii"),
        "Supplied SRV reference",
    )
    return review


def correct(review: Review, scope: str, changes: dict[str, str], reason: str) -> None:
    if not reason.strip():
        raise ValueError("Explain the source or reason for this correction.")
    if len(reason) > 1000 or any(len(v) > 500 for v in changes.values()):
        raise ValueError("Correction values or reason exceed supported length.")
    if scope == "filing":
        original = {key: "unknown" for key in DECLARATIONS}
        target = review.filing_declarations
        if set(changes) - set(DECLARATIONS):
            raise ValueError("Unknown shared review question.")
        for key, value in changes.items():
            if value not in DECLARATIONS[key][1]:
                raise ValueError("Invalid shared review answer.")
    elif scope == "context":
        original = asdict(review.source.context)
        target = review.context_overrides
        if set(changes) - set(original):
            raise ValueError("Unknown employer field.")
    else:
        row = next((r for r in review.source.rows if r.key == scope), None)
        if row is None:
            raise ValueError("Unknown employee row.")
        original = row.values | {key: "unknown" for key in DECLARATIONS}
        target = review.overrides.setdefault(scope, {})
        if set(changes) - (set(HEADERS) | set(DECLARATIONS)):
            raise ValueError("Unknown employee field.")
        for key, (_, options) in DECLARATIONS.items():
            if key in changes and changes[key] not in [*options, "inherit"]:
                raise ValueError("Invalid review declaration.")
    now = datetime.now(UTC).isoformat()
    for key, value in changes.items():
        value = value.strip()
        destination = (
            review.declarations.setdefault(scope, {})
            if key in DECLARATIONS and scope != "filing"
            else target
        )
        before = destination.get(
            key, "inherit" if key in DECLARATIONS and scope != "filing" else original.get(key, "")
        )
        if key in DECLARATIONS and scope != "filing" and value == "inherit":
            if key in destination:
                before = destination.pop(key)
                review.history.append(
                    Correction(scope, key, before, "inherit", reason.strip(), now)
                )
            continue
        if value == before:
            continue
        destination[key] = value
        review.history.append(Correction(scope, key, before, value, reason.strip(), now))
    review.revision += 1


def status(review: Review) -> str:
    snapshot = build_snapshot(review)
    if not snapshot.valid:
        return "Needs correction"
    if review.evidence and digest(serialize(snapshot)) == review.evidence.dat_hash:
        return "Official validation evidence attached"
    return "Ready for BIR validation"


def audit(review: Review) -> dict[str, object]:
    snapshot = build_snapshot(review)
    return {
        "profile": snapshot.profile,
        "source_hash": review.source.sha256,
        "source_file": review.source.filename,
        "sheet": review.source.sheet,
        "revision": review.revision,
        "status": status(review),
        "export_purpose": "Candidate DAT for official BIR validation; not proof of approval or filing",
        "encoding": snapshot.context.encoding,
        "automatic_mappings": [asdict(m) for m in snapshot.mappings],
        "blocking_issues": [asdict(i) for i in snapshot.issues if i.severity == "error"],
        "review_notes": [asdict(i) for i in snapshot.issues if i.severity == "warning"],
        "output_hash": digest(serialize(snapshot)) if snapshot.valid else None,
        "context": asdict(snapshot.context),
        "original_context": asdict(review.source.context),
        "source_rows": [asdict(row) for row in review.source.rows],
        "overrides": review.overrides,
        "declarations": review.declarations,
        "filing_declarations": review.filing_declarations,
        "effective_declarations": {
            row.key: effective_declarations(review, row) for row in review.source.rows
        },
        "corrections": [asdict(c) for c in review.history],
        "issues": [asdict(i) for i in snapshot.issues],
        "totals": {
            key: str(snapshot.total(key)) if snapshot.total(key) is not None else None
            for key in ("I", "O", "P", "AQ", "AR", "AS")
        },
        "evidence": asdict(review.evidence) if review.evidence else None,
        "evidence_matches_current_output": bool(
            snapshot.valid
            and review.evidence
            and digest(serialize(snapshot)) == review.evidence.dat_hash
        ),
    }
