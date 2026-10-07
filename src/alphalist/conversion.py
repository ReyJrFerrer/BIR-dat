"""Pure normalization, mapping and conservative profile validation."""

import re
from dataclasses import asdict
from datetime import date
from decimal import Decimal, InvalidOperation

from .domain import (
    ZERO,
    EmployeeAnnualRecord,
    FilingContext,
    Review,
    Snapshot,
    SourceRow,
    ValidationIssue,
)

MONEY = ("E F G H I J K L M N O P Q R S T U AJ AK AL AM AN AO AP AQ AR AS AT").split()
PRIOR = "AJ AK AL AM AN AO AP AQ".split()
DECLARATIONS = {
    "schedule": ("Employee classification", ["unknown", "non_mwe", "mwe"]),
    "prior": ("Previous employment in reporting year", ["unknown", "none", "present"]),
    "withholding": (
        "P / AR represent finalized withholding and annual tax",
        ["unknown", "confirmed"],
    ),
    "tax_treatment": ("Ordinary graduated annual tax treatment", ["unknown", "confirmed"]),
    "benefits": ("Non-taxable categories and annual exclusion reviewed", ["unknown", "confirmed"]),
    "substituted": ("Substituted-filing eligibility reviewed", ["unknown", "confirmed"]),
}
SUMMARY_FIELDS = {
    "I": "Present non-taxable",
    "O": "Present taxable",
    "P": "Present final withholding",
    "AQ": "Previous withholding",
    "AR": "Annual tax due",
    "AS": "Present Jan–Nov withholding",
}


def money(value: str) -> Decimal | None:
    if not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", value):
        return None
    try:
        result = Decimal(value)
        return result if result.is_finite() and abs(result) < Decimal("1000000000000") else None
    except InvalidOperation:
        return None


def fmt(value: Decimal) -> str:
    return f"{value:.2f}"


def identifier(value: str, digits: int) -> str:
    if not re.fullmatch(r"[0-9 -]+", value):
        return ""
    result = re.sub(r"[ -]", "", value)
    return result if len(result) == digits else ""


def ordinary_tax(income: Decimal) -> Decimal:
    # Pinned 2025 ordinary graduated treatment, only used after explicit classification.
    for threshold, base, rate in [
        ("8000000", "2202500", ".35"),
        ("2000000", "402500", ".30"),
        ("800000", "102500", ".25"),
        ("400000", "22500", ".20"),
        ("250000", "0", ".15"),
    ]:
        if income > Decimal(threshold):
            from decimal import ROUND_HALF_UP

            return (Decimal(base) + (income - Decimal(threshold)) * Decimal(rate)).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )
    return ZERO


def effective_declarations(review: Review, row: SourceRow) -> dict[str, str]:
    """Explicit employee decisions override shared answers, including 'unknown'."""
    values = row.values | review.overrides.get(row.key, {})
    answers = review.filing_declarations | review.declarations.get(row.key, {})
    # Populated prior-employer data already establishes presence. The shared
    # no-prior answer applies only to empty blocks; never erase an existing block.
    populated = any(values[k] for k in ("AE", "AF", "AG", "AH", "AI")) or any(
        values[k] and money(values[k]) != ZERO for k in PRIOR
    )
    if populated and "prior" not in review.declarations.get(row.key, {}):
        answers["prior"] = "present"
    return answers


def build_snapshot(review: Review) -> Snapshot:
    context = FilingContext(**(asdict(review.source.context) | review.context_overrides))
    issues: list[ValidationIssue] = []

    def issue(
        code: str,
        field: str,
        observed: str,
        message: str,
        remedy: str,
        row_key: str = "",
        employee: str = "",
        cell: str = "",
        severity: str = "error",
        category: str = "data",
    ) -> None:
        issues.append(
            ValidationIssue(
                "warning" if severity == "warning" else "error",
                code,
                employee,
                row_key,
                cell,
                field,
                observed,
                message,
                remedy,
                category,
            )
        )

    if not context.name.strip():
        issue(
            "EMPLOYER_NAME",
            "name",
            context.name,
            "Employer name is missing.",
            "Enter the withholding agent name.",
        )
    tin = identifier(context.tin, 9)
    if not tin:
        issue(
            "EMPLOYER_TIN",
            "tin",
            context.tin,
            "A nine-digit employer TIN is required.",
            "Enter the actual employer TIN when available.",
        )
    if not re.fullmatch(r"\d{4}", context.branch, flags=re.ASCII):
        issue(
            "EMPLOYER_BRANCH",
            "branch",
            context.branch,
            "A four-digit employer branch is required by this profile.",
            "Enter the actual branch, preserving leading zeros.",
        )
    if context.year != "2025":
        issue(
            "YEAR_PROFILE",
            "year",
            context.year,
            "This profile is pinned to reporting year 2025.",
            "Use 2025 data; other years require a verified profile.",
            category="profile",
        )
    context = FilingContext(context.name, tin or context.tin, context.branch, context.year)
    records = []
    ids: set[str] = set()
    tins: set[str] = set()
    for row in review.source.rows:
        values = row.values | review.overrides.get(row.key, {})
        declarations = effective_declarations(review, row)

        def problem(
            code: str,
            field: str,
            message: str,
            remedy: str,
            severity: str = "error",
            category: str = "data",
            values: dict[str, str] = values,
            declarations: dict[str, str] = declarations,
            row: SourceRow = row,
        ) -> None:
            issue(
                code,
                field,
                values.get(field, declarations.get(field, "")),
                message,
                remedy,
                row.key,
                values["A"],
                row.cells.get(field, ""),
                severity,
                category,
            )

        if not values["A"] or values["A"] in ids:
            problem(
                "EMPLOYEE_ID",
                "A",
                "Employee ID is missing or duplicated.",
                "Supply a unique source employee ID; no rows will be omitted.",
            )
        ids.add(values["A"])
        emp_tin = identifier(values["V"], 13)
        if not emp_tin:
            problem(
                "EMPLOYEE_TIN",
                "V",
                "Employee TIN/branch must contain 9 + 4 digits.",
                "Enter the actual TIN and branch; do not use placeholders.",
            )
        elif emp_tin[:9] in tins:
            problem(
                "DUPLICATE_TIN",
                "V",
                "Another employee has this TIN.",
                "Review the duplicate records and source identifiers.",
            )
        tins.add(emp_tin[:9])
        for field in ("W", "X"):
            if not values[field]:
                problem(
                    "NAME_REQUIRED",
                    field,
                    "Required name component is missing.",
                    "Enter the source surname or given name.",
                )
        if not values["Y"]:
            problem(
                "MIDDLE_NAME",
                "Y",
                "Middle name is blank.",
                "Review; a genuinely absent middle name may stay blank.",
                "warning",
            )
        for field in ("W", "X", "Y"):
            value = values[field]
            if (
                not value.isascii()
                or any(c in value for c in '",\r\n')
                or any(ord(c) < 32 for c in value)
            ):
                problem(
                    "NAME_ENCODING",
                    field,
                    "Name requires unverified encoding or escaping rules.",
                    "Preserve the name. A verified BIR character profile is required.",
                    category="profile",
                )
            if len(value) > 50:
                problem(
                    "NAME_WIDTH",
                    field,
                    "Name exceeds the conservative 50-character limit.",
                    "Verify the applicable field width; never truncate a real name.",
                    category="profile",
                )
        parsed_dates: dict[str, date] = {}
        for field in ("C", "D"):
            try:
                parsed_dates[field] = date.fromisoformat(values[field])
                if str(parsed_dates[field].year) != context.year:
                    raise ValueError
            except ValueError:
                problem(
                    "EMPLOYMENT_DATE",
                    field,
                    "Employment date must be a valid ISO date within the filing year.",
                    "Use YYYY-MM-DD and confirm the reporting-period policy.",
                )
        if len(parsed_dates) == 2 and parsed_dates["C"] > parsed_dates["D"]:
            problem(
                "DATE_ORDER",
                "D",
                "Employment ends before it begins.",
                "Correct the employment dates.",
            )
        prior_populated = any(values[k] for k in ("AE", "AF", "AG", "AH", "AI")) or any(
            values[k] and money(values[k]) != ZERO for k in PRIOR
        )
        prior_state = declarations.get("prior", "unknown")
        if prior_state == "none" and prior_populated:
            problem(
                "PRIOR_CONFLICT",
                "AE",
                "No-prior-employer declaration conflicts with source values.",
                "Review the declaration and previous-employer fields.",
            )
        if prior_state == "unknown":
            problem(
                "PRIOR_REVIEW",
                "prior",
                "Previous-employer state has not been confirmed.",
                "Record a supported declaration when evidence is available.",
                category="review",
            )
        has_prior = prior_populated or prior_state == "present"
        amounts: dict[str, Decimal | None] = {}
        for field in MONEY:
            if field in PRIOR and not values[field] and not has_prior:
                # For draft source reconciliation only; unknown prior state remains a blocker.
                amounts[field] = ZERO
                continue
            amounts[field] = money(values[field])
            parsed_amount = amounts[field]
            if parsed_amount is None:
                problem(
                    "AMOUNT",
                    field,
                    "Amount is missing or is not a decimal with at most two places.",
                    "Enter a source-supported amount; formula cells need cached values. Blank is not zero.",
                )
            elif parsed_amount < ZERO and field not in ("K", "Q"):
                problem(
                    "NEGATIVE_AMOUNT",
                    field,
                    "This compensation/withholding field cannot be negative.",
                    "Review its source sign and classification.",
                )

        def total(*fields: str, amounts: dict[str, Decimal | None] = amounts) -> Decimal | None:
            vals = [amounts[k] for k in fields]
            return (
                None
                if any(v is None for v in vals)
                else sum((v for v in vals if v is not None), ZERO)
            )

        for result, components in [
            ("I", ("E", "F", "G", "H")),
            ("L", ("J", "K")),
            ("O", ("L", "M", "N")),
        ]:
            calculated = total(*components)
            if (
                calculated is not None
                and amounts[result] is not None
                and calculated != amounts[result]
            ):
                problem(
                    "ARITHMETIC",
                    result,
                    f"{result} does not equal {' + '.join(components)} ({fmt(calculated)}).",
                    "Correct the source-supported amounts; totals are not silently repaired.",
                )
        if total("G", "K") not in (None, ZERO):
            problem(
                "CONTRIBUTIONS",
                "K",
                "Positive and negative contribution entries do not reconcile.",
                "Review G and K; do not subtract contributions twice.",
            )
        amounts["prior_nontax"] = total("AJ", "AK", "AL", "AM")
        amounts["prior_taxable"] = total("AN", "AO", "AP")
        amounts["prior_gross"] = total("prior_nontax", "prior_taxable")
        amounts["gross"] = total("I", "O")
        amounts["combined_taxable"] = total("prior_taxable", "O")
        amounts["adjusted"] = total("AQ", "P")
        amounts["additional"] = None
        amounts["refund"] = None
        if amounts["P"] is not None and amounts["AS"] is not None:
            delta = amounts["P"] - amounts["AS"]
            amounts["additional"] = max(delta, ZERO)
            amounts["refund"] = max(-delta, ZERO)
            if delta < ZERO:
                problem(
                    "REFUND_PROFILE",
                    "P",
                    f"Potential refund: {fmt(-delta)}. Payment and field behavior are unverified.",
                    "Preserve this difference; official-app refund evidence is needed.",
                    category="profile",
                )
        if has_prior:
            problem(
                "PRIOR_PROFILE",
                "AE",
                "Previous-employer mappings require an additional official-app fixture.",
                "Verify D1 fields 37, 38 and 44 before enabling final export.",
                category="profile",
            )
            if not identifier(values["AE"], 13):
                problem(
                    "PRIOR_TIN",
                    "AE",
                    "Previous-employer TIN/branch is missing or invalid.",
                    "Enter the previous employer identifier from source evidence.",
                )
            for field in ("AF", "AG", "AH"):
                if not values[field]:
                    problem(
                        "PRIOR_REQUIRED",
                        field,
                        "Previous-employer information is incomplete.",
                        "Supply the documented value.",
                    )
            try:
                start, end = date.fromisoformat(values["AG"]), date.fromisoformat(values["AH"])
                if start > end or str(start.year) != context.year or str(end.year) != context.year:
                    raise ValueError
            except ValueError:
                problem(
                    "PRIOR_DATES",
                    "AG",
                    "Previous-employer dates are invalid for this year.",
                    "Review start and end dates.",
                )
        for field, allowed in [
            ("AA", {"R"}),
            ("AB", {"", "NA"}),
            ("AC", {"NCR"}),
            ("Z", {"FILIPINO"}),
        ]:
            if values[field].upper() not in allowed:
                problem(
                    "CODE_PROFILE",
                    field,
                    "This code/treatment is outside the supplied verified fixture.",
                    "Preserve valid source codes; extend the profile using official evidence.",
                    category="profile",
                )
        if values["AD"].lower() not in ("yes", "no"):
            problem(
                "SUBSTITUTED_VALUE",
                "AD",
                "Substituted filing must be Yes or No.",
                "Correct the source value.",
            )
        if has_prior and values["AD"].lower() == "yes":
            problem(
                "SUBSTITUTED_PRIOR",
                "AD",
                "Previous employment requires substituted-filing eligibility review.",
                "Review eligibility using the applicable official rules.",
            )
        for field in DECLARATIONS:
            if field == "prior":
                continue
            expected = "non_mwe" if field == "schedule" else "confirmed"
            if declarations.get(field) != expected:
                problem(
                    "CLASSIFICATION",
                    field,
                    "Schedule 2 is unsupported."
                    if declarations.get(field) == "mwe"
                    else f"{DECLARATIONS[field][0]} is unresolved.",
                    "Record a declaration only when supported by evidence; otherwise leave unresolved.",
                    category="review",
                )
        if amounts["AT"] not in (None, ZERO):
            problem(
                "PERA_PROFILE",
                "AT",
                "Nonzero PERA is not verified by the supplied fixture.",
                "Additional official-app evidence is required.",
                category="profile",
            )
        if amounts["H"] not in (None, ZERO) or (total("E", "H", "AJ", "AM") or ZERO) > Decimal(
            "90000"
        ):
            problem(
                "BENEFIT_PROFILE",
                "H",
                "Benefit classification/exclusion needs a separately verified mapping.",
                "Do not automatically cap or reclassify source compensation.",
                category="profile",
            )
        if amounts["combined_taxable"] is not None and amounts["combined_taxable"] <= Decimal(
            "250000"
        ):
            problem(
                "LOW_INCOME_PROFILE",
                "O",
                "Low-income non-MWE field treatment needs official-app verification.",
                "Income alone does not establish MWE status.",
                category="profile",
            )
        if (
            amounts["adjusted"] is not None
            and amounts["AR"] is not None
            and amounts["adjusted"] != amounts["AR"]
        ):
            problem(
                "WITHHOLDING_RECONCILIATION",
                "AR",
                "Annual tax and combined final withholding differ.",
                "Review the annualization and withholding source values.",
            )
        if (
            declarations.get("tax_treatment") == "confirmed"
            and amounts["combined_taxable"] is not None
            and amounts["AR"] is not None
            and amounts["AT"] == ZERO
        ):
            expected_tax = ordinary_tax(amounts["combined_taxable"])
            if expected_tax != amounts["AR"]:
                problem(
                    "ANNUAL_TAX",
                    "AR",
                    f"Ordinary graduated annual tax would be {fmt(expected_tax)}.",
                    "Review annual tax and the declared tax treatment.",
                )
        if amounts["S"] is not None and amounts["AR"] is not None and amounts["S"] != amounts["AR"]:
            problem(
                "ESTIMATE_DIFFERENCE",
                "S",
                "Estimated tax differs from supplied annual tax AR.",
                "AR is retained; S is diagnostic only.",
                "warning",
            )
        detail = None
        if all(v is not None for v in amounts.values()) and len(parsed_dates) == 2:

            def m(field: str, amounts: dict[str, Decimal | None] = amounts) -> str:
                value = amounts[field]
                assert value is not None
                return fmt(value)

            period = f"12/31/{context.year}"
            detail = tuple(
                [
                    "D1",
                    "1604C",
                    context.tin,
                    context.branch,
                    period,
                    "0",
                    emp_tin[:9],
                    emp_tin[9:],
                    values["W"].upper(),
                    values["X"].upper(),
                    values["Y"].upper(),
                    values["AC"].upper(),
                    m("prior_gross"),
                    "0.00",
                    m("AJ"),
                    m("AK"),
                    m("AL"),
                    m("AM"),
                    m("prior_nontax"),
                    m("AN"),
                    m("AO"),
                    m("AP"),
                    m("prior_taxable"),
                    parsed_dates["C"].strftime("%m/%d/%Y"),
                    parsed_dates["D"].strftime("%m/%d/%Y"),
                    m("gross"),
                    "0.00",
                    m("E"),
                    m("F"),
                    m("G"),
                    m("H"),
                    m("I"),
                    m("L"),
                    m("M"),
                    m("N"),
                    m("O"),
                    m("combined_taxable"),
                    m("combined_taxable"),
                    m("AR"),
                    m("AQ"),
                    m("AS"),
                    m("additional"),
                    m("refund"),
                    m("adjusted"),
                    values["Z"].upper(),
                    values["AA"].upper(),
                    values["AB"].upper() or "NA",
                    "Y" if values["AD"].lower() == "yes" else "N",
                    m("AT"),
                ]
            )
        records.append(
            EmployeeAnnualRecord(
                row.key,
                values["A"],
                f"{values['W']}, {values['X']} {values['Y']}".strip(),
                values["V"],
                tuple(values.items()),
                tuple(amounts.items()),
                detail,
            )
        )
    # Source controls are checked against original rows, never against edited totals.
    for key, control in review.source.totals.items():
        if key not in MONEY or not control:
            continue
        parsed = [money(row.values[key]) for row in review.source.rows]
        if all(v is not None for v in parsed) and sum(
            (v for v in parsed if v is not None), ZERO
        ) != money(control):
            issue(
                "SOURCE_TOTAL",
                key,
                control,
                "Workbook TOTAL does not match its original employee rows.",
                "Obtain a reconciled workbook; this source discrepancy is not erased by overrides.",
            )
    # Multi-employee ordering has not been established by a one-record fixture.
    if len(records) > 1:
        issue(
            "ORDERING_PROFILE",
            "profile",
            "",
            "Multi-employee ordering has not been verified in the official app.",
            "Verify alphabetical ordering and tie-breaking before enabling multi-employee final export.",
            category="profile",
        )
    return Snapshot(context, tuple(records), tuple(issues), review.source.sha256)
