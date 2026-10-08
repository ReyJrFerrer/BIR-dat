"""Deterministic source-preserving mappings for export to the official validator."""

import re
from dataclasses import asdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .domain import (
    ZERO,
    AutomaticMapping,
    EmployeeAnnualRecord,
    FilingContext,
    Review,
    Snapshot,
    SourceRow,
    ValidationIssue,
)
from .profiles import (
    EMPLOYMENT_CODES,
    ENCODINGS,
    FIXTURE_SOURCE,
    LAYOUT_SOURCE,
    NAME_CHARACTERS,
    NAME_POLICY,
    REGION_CODES,
    SEPARATION_CODES,
    SORT_POLICY,
    SOURCE_POLICY,
    normalize_name,
    sort_key,
    uppercase_name,
)

MONEY = "E F G H I J K L M N O P Q R S T U AJ AK AL AM AN AO AP AQ AR AS AT".split()
DIAGNOSTICS = frozenset("Q R S T U".split())
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
    # Employee branch 0000 is valid in the reference; an all-zero TIN is a dummy.
    return result if len(result) == digits and result[:9] != "000000000" else ""


def ordinary_tax(income: Decimal) -> Decimal:
    """2025 ordinary annual table; never inferred from nationality."""
    for threshold, base, rate in [
        ("8000000", "2202500", ".35"),
        ("2000000", "402500", ".30"),
        ("800000", "102500", ".25"),
        ("400000", "22500", ".20"),
        ("250000", "0", ".15"),
    ]:
        if income > Decimal(threshold):
            return (Decimal(base) + (income - Decimal(threshold)) * Decimal(rate)).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )
    return ZERO


def prior_populated(values: dict[str, str]) -> bool:
    return any(values[k] for k in ("AE", "AF", "AG", "AH", "AI")) or any(
        values[k] and money(values[k]) != ZERO for k in PRIOR
    )


def effective_declarations(review: Review, row: SourceRow) -> dict[str, str]:
    """Only explicit declarations are confirmations; source presence is observable."""
    values = row.values | review.overrides.get(row.key, {})
    answers = review.filing_declarations | review.declarations.get(row.key, {})
    if prior_populated(values) and "prior" not in review.declarations.get(row.key, {}):
        answers["prior"] = "present"
    return answers


def build_snapshot(review: Review) -> Snapshot:
    context = FilingContext(**(asdict(review.source.context) | review.context_overrides))
    issues: list[ValidationIssue] = []
    mappings: list[AutomaticMapping] = []

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
    elif tin != context.tin:
        mappings.append(
            AutomaticMapping(
                "IDENTIFIERS",
                "",
                "",
                "tin",
                "",
                context.tin,
                tin,
                "Removed presentation separators; digits retained.",
                FIXTURE_SOURCE,
            )
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
            "Use a profile for the actual reporting year.",
            category="profile",
        )
    if context.encoding not in ENCODINGS:
        issue(
            "EXPORT_ENCODING",
            "encoding",
            context.encoding,
            "Export encoding is not supported.",
            "Choose Windows-1252 or UTF-8.",
        )
    context = FilingContext(
        context.name, tin or context.tin, context.branch, context.year, context.encoding
    )
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

        def mapped(
            code: str,
            field: str,
            after: str,
            reason: str,
            basis: str,
            before: str | None = None,
            row: SourceRow = row,
            values: dict[str, str] = values,
        ) -> None:
            mappings.append(
                AutomaticMapping(
                    code,
                    values["A"],
                    row.key,
                    field,
                    row.cells.get(field, ""),
                    values.get(field, "") if before is None else before,
                    after,
                    reason,
                    basis,
                )
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
        else:
            mapped(
                "IDENTIFIERS",
                "V",
                f"{emp_tin[:9]}/{emp_tin[9:]}",
                "Separated employee TIN and branch without changing any digits.",
                FIXTURE_SOURCE,
            )
        tins.add(emp_tin[:9])
        export_names = {}
        for field in ("W", "X", "Y"):
            value = values[field]
            export_value = normalize_name(value)
            export_names[field] = export_value
            if not export_value and field != "Y":
                problem(
                    "NAME_REQUIRED",
                    field,
                    "Required name component is empty after export normalization.",
                    "Enter the actual surname or given name; apostrophes alone are not a name.",
                )
            if any(ord(c) < 32 or ord(c) == 127 for c in value):
                problem(
                    "NAME_CONTROL",
                    field,
                    "Name contains a line break or control character.",
                    "Correct the source text; embedded record delimiters are not allowed.",
                )
            try:
                if context.encoding in ENCODINGS:
                    export_value.encode(context.encoding, errors="strict")
            except UnicodeEncodeError:
                problem(
                    "NAME_ENCODING",
                    field,
                    f"Name cannot be represented without loss in {context.encoding}.",
                    "Supply a supported export spelling. Changing encoding does not resolve unsupported name characters.",
                )
            unsupported = sorted(
                c for c in set(export_value) - NAME_CHARACTERS if ord(c) >= 32 and ord(c) != 127
            )
            if unsupported:
                problem(
                    "NAME_CHARACTERS",
                    field,
                    "Unsupported export name character(s): " + ", ".join(repr(c) for c in unsupported) + ".",
                    "Use a documented spelling with A–Z, spaces, hyphens or periods. Ñ and apostrophes are normalized automatically; other characters are not silently removed.",
                )
            if len(export_value) > 50:
                problem(
                    "NAME_WIDTH",
                    field,
                    "Name exceeds the conservative 50-character field limit.",
                    "Verify supported field width; names are never truncated.",
                )
            if export_value != value:
                mapped(
                    "NAME_NORMALIZATION" if export_value != uppercase_name(value) else "NAMES",
                    field,
                    export_value,
                    "Uppercase for export; replace Ñ/ñ with N and remove apostrophes. Original spelling retained; other unsupported characters block export.",
                    NAME_POLICY,
                )
        if not export_names["Y"]:
            problem(
                "MIDDLE_NAME",
                "Y",
                "Middle name is blank.",
                "A genuinely absent middle name may stay blank.",
                "warning",
            )
        parsed_dates: dict[str, date] = {}
        for field in ("C", "D"):
            try:
                parsed = date.fromisoformat(values[field])
                if str(parsed.year) != context.year:
                    raise ValueError
                parsed_dates[field] = parsed
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
        populated = prior_populated(values)
        prior_state = declarations.get("prior", "unknown")
        if prior_state == "none" and populated:
            problem(
                "PRIOR_CONFLICT",
                "AE",
                "No-prior-employer declaration conflicts with source values.",
                "Review the declaration and previous-employer fields.",
            )
        has_prior = populated or prior_state == "present"
        if not has_prior:
            mapped(
                "PREVIOUS_EMPLOYER",
                "AE",
                "No previous employer recorded; monetary fields 0.00",
                "Empty prior-employer block is represented as absent in this source-preserving candidate.",
                SOURCE_POLICY,
            )
            if prior_state == "unknown":
                problem(
                    "PRIOR_REVIEW",
                    "prior",
                    "No previous employer is recorded in the workbook.",
                    "Candidate uses zero previous compensation; this does not confirm employment history.",
                    "warning",
                    "review",
                )
        derived_inputs = dict(values)
        for derived_field, components in [
            ("I", ("E", "F", "G", "H")),
            ("L", ("J", "K")),
            ("O", ("L", "M", "N")),
        ]:
            if derived_inputs[derived_field]:
                continue
            inputs = [money(derived_inputs[k]) for k in components]
            if all(value is not None for value in inputs):
                derived_inputs[derived_field] = fmt(sum((v for v in inputs if v is not None), ZERO))
                mapped(
                    "TOTALS",
                    derived_field,
                    derived_inputs[derived_field],
                    f"Derived missing total from {' + '.join(components)}. Source cell remains unchanged.",
                    "Supplied annualization column relationships",
                )
        amounts: dict[str, Decimal | None] = {}
        for field in MONEY:
            if field in PRIOR and not values[field] and not has_prior:
                amounts[field] = ZERO
                continue
            amounts[field] = money(derived_inputs[field])
            parsed_amount = amounts[field]
            severity = "warning" if field in DIAGNOSTICS else "error"
            if parsed_amount is None:
                if field not in DIAGNOSTICS or values[field]:
                    problem(
                        "AMOUNT",
                        field,
                        "Amount is missing or is not a decimal with at most two places.",
                        "Enter a source-supported amount; required blanks are not zero.",
                        severity,
                    )
            elif parsed_amount < ZERO and field not in ("K", "Q"):
                problem(
                    "NEGATIVE_AMOUNT",
                    field,
                    "This compensation/withholding field cannot be negative.",
                    "Review the source sign and classification.",
                    severity,
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
                "Review G and K; contributions are not subtracted twice.",
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
            mapped(
                "YEAR_END",
                "P",
                f"December {fmt(max(delta, ZERO))}; refund {fmt(max(-delta, ZERO))}",
                "Positive P − AS maps to collection; negative difference maps to refund, never negative collection.",
                LAYOUT_SOURCE,
            )
            if delta < ZERO:
                problem(
                    "REFUND_PAYMENT",
                    "P",
                    f"Computed refund: {fmt(-delta)}; actual payment is not established by this calculation.",
                    "Candidate preserves the supplied final withholding and reports the calculated refund.",
                    "warning",
                    "review",
                )
        if has_prior:
            if not identifier(values["AE"], 13):
                problem(
                    "PRIOR_TIN",
                    "AE",
                    "Previous-employer TIN/branch is missing or invalid.",
                    "Enter the source previous-employer identifier.",
                )
            for field in ("AF", "AG", "AH"):
                if not values[field]:
                    problem(
                        "PRIOR_REQUIRED",
                        field,
                        "Previous-employer information is incomplete.",
                        "Supply the documented value.",
                    )
            for field, allowed in [("AF", EMPLOYMENT_CODES), ("AI", SEPARATION_CODES)]:
                if values[field].upper() not in allowed:
                    problem(
                        "PRIOR_CODE",
                        field,
                        "Previous-employer code is unrecognized.",
                        "Use a documented employment or separation code.",
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
            for derived, expression in [
                ("prior_taxable", "AN + AO + AP"),
                ("combined_taxable", "prior taxable + O"),
                ("adjusted", "AQ + P"),
            ]:
                derived_value = amounts[derived]
                if derived_value is not None:
                    mapped(
                        "PREVIOUS_EMPLOYER",
                        derived,
                        fmt(derived_value),
                        expression,
                        LAYOUT_SOURCE,
                    )
            problem(
                "PRIOR_VALIDATION",
                "AE",
                "Previous-employer values are included and reconciled.",
                "Confirm the candidate field semantics using the target official validator.",
                "warning",
                "profile",
            )
        for field, allowed in [
            ("AA", EMPLOYMENT_CODES),
            ("AB", SEPARATION_CODES),
            ("AC", REGION_CODES),
        ]:
            code = values[field].upper()
            if code not in allowed:
                problem(
                    "INVALID_CODE",
                    field,
                    "Employee code is unrecognized.",
                    "Use a supported employment, separation or region code; valid source data is never replaced with a guess.",
                )
            else:
                mapped(
                    "CODES",
                    field,
                    code or "NA",
                    "Validated the code; normalized case and absent separation reason.",
                    LAYOUT_SOURCE if field != "AC" else SOURCE_POLICY,
                )
        if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,49}", values["Z"]):
            problem(
                "NATIONALITY",
                "Z",
                "Nationality is missing or is not a supported text value.",
                "Supply the nationality text; tax residency is reviewed separately.",
            )
        elif values["Z"].upper() != "FILIPINO":
            problem(
                "FOREIGN_TAX_TREATMENT",
                "Z",
                "Nationality is retained; tax residency is not inferred.",
                "Review the supplied annual tax for the employee’s actual treatment.",
                "warning",
                "review",
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
                "Substituted filing Yes conflicts with previous employment in this year.",
                "Review eligibility and correct the source-supported answer.",
            )
        for field in DECLARATIONS:
            if field == "prior":
                continue
            expected = "non_mwe" if field == "schedule" else "confirmed"
            if declarations.get(field) == expected:
                continue
            if field == "schedule" and declarations.get(field) == "mwe":
                problem(
                    "UNSUPPORTED_MWE",
                    field,
                    "Declared minimum wage earners require Schedule 2, which is unsupported.",
                    "Use a verified Schedule 2 converter.",
                    category="profile",
                )
            else:
                problem(
                    "CLASSIFICATION",
                    field,
                    f"{DECLARATIONS[field][0]} has not been independently confirmed.",
                    "Source values are retained for validation. You may leave this review answer unknown.",
                    "warning",
                    "review",
                )
        if amounts["AT"] not in (None, ZERO):
            problem(
                "PERA_PROFILE",
                "AT",
                "Nonzero PERA requires a separately implemented and verified mapping.",
                "Do not change the credit to zero to enable export.",
                category="profile",
            )
        benefit_sum = total("E", "H", "AJ", "AM")
        if (
            amounts["H"] not in (None, ZERO)
            or benefit_sum is not None
            and benefit_sum > Decimal("90000")
        ):
            problem(
                "BENEFIT_REVIEW",
                "H",
                "Source non-taxable categories are retained; classification/exclusion needs review.",
                "No automatic cap or reclassification is applied. Resolve any proven classification error in the source values.",
                "warning",
                "review",
            )
        mapped(
            "BENEFITS",
            "H",
            values["H"],
            "Preserved source benefit categories; component totals checked; no payroll reclassification.",
            SOURCE_POLICY,
        )
        if amounts["combined_taxable"] is not None and amounts["combined_taxable"] <= Decimal(
            "250000"
        ):
            mapped(
                "LOW_INCOME",
                "O",
                fmt(amounts["combined_taxable"]),
                "Preserved source compensation and annual tax; income alone does not determine MWE status.",
                SOURCE_POLICY,
            )
            problem(
                "LOW_INCOME_VALIDATION",
                "O",
                "Source taxable/exempt allocation is preserved for this low-income employee.",
                "Confirm field allocation in the target validator. The converter does not move pay to exempt fields solely from income.",
                "warning",
                "profile",
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
        if (
            all(v is not None for k, v in amounts.items() if k not in DIAGNOSTICS)
            and len(parsed_dates) == 2
        ):

            def m(field: str, amounts: dict[str, Decimal | None] = amounts) -> str:
                value = amounts[field]
                assert value is not None
                return fmt(value)

            detail = tuple(
                [
                    "D1",
                    "1604C",
                    context.tin,
                    context.branch,
                    f"12/31/{context.year}",
                    "0",
                    emp_tin[:9],
                    emp_tin[9:],
                    export_names["W"],
                    export_names["X"],
                    export_names["Y"],
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
    for key, control in review.source.totals.items():
        if key not in MONEY or not control:
            continue
        source_amounts = [money(row.values[key]) for row in review.source.rows]
        if all(v is not None for v in source_amounts) and sum(
            (v for v in source_amounts if v is not None), ZERO
        ) != money(control):
            issue(
                "SOURCE_TOTAL",
                key,
                control,
                "Workbook TOTAL does not match its original employee rows.",
                "Obtain a reconciled workbook; this source discrepancy is not erased by overrides.",
                severity="warning" if key in DIAGNOSTICS else "error",
            )
    # Assign order once, so review, PDF, DAT and audit use identical sequences.
    records.sort(key=lambda record: sort_key(dict(record.source)))
    for sequence, record in enumerate(records, 1):
        mappings.append(
            AutomaticMapping(
                "ORDERING",
                record.employee_id,
                record.key,
                "sequence",
                "",
                "",
                str(sequence),
                SORT_POLICY,
                SOURCE_POLICY,
            )
        )
    return Snapshot(
        context, tuple(records), tuple(issues), review.source.sha256, mappings=tuple(mappings)
    )
