"""Prepare the 2025 San Diego Get It Done data for analysis and modeling.

The script validates the raw source, records data-quality measures, sanitizes
free text, derives modeling fields, and writes a compressed local dataset.
The raw and prepared record-level files are intentionally excluded from Git.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = Path("data/raw/get_it_done_requests_closed_2025_datasd.csv")
DEFAULT_OUTPUT = Path(
    "data/processed/get_it_done_requests_closed_2025_prepared.csv.gz"
)
DEFAULT_TABLE_DIR = Path("outputs/tables")

EXPECTED_COLUMNS = {
    "service_request_id",
    "service_request_parent_id",
    "date_requested",
    "case_age_days",
    "case_record_type",
    "service_name",
    "service_name_detail",
    "date_closed",
    "status",
    "lat",
    "lng",
    "street_address",
    "zipcode",
    "council_district",
    "comm_plan_name",
    "case_origin",
    "public_description",
}

STRING_COLUMNS = {
    "service_request_id": "string",
    "service_request_parent_id": "string",
    "sap_notification_number": "string",
    "case_record_type": "string",
    "service_name": "string",
    "service_name_detail": "string",
    "status": "string",
    "street_address": "string",
    "zipcode": "string",
    "council_district": "string",
    "comm_plan_code": "string",
    "comm_plan_name": "string",
    "park_name": "string",
    "case_origin": "string",
    "referred": "string",
    "iamfloc": "string",
    "floc": "string",
    "public_description": "string",
}

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE
)
URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?1[\s.()-]*)?(?:\(?\d{3}\)?[\s.()-]*)"
    r"\d{3}[\s.-]*\d{4}(?!\d)"
)
ADDRESS_PATTERN = re.compile(
    r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?"
    r"(?:[A-Z0-9.'-]+\s+){1,5}"
    r"(?:STREET|ST|AVENUE|AVE|ROAD|RD|BOULEVARD|BLVD|DRIVE|DR|"
    r"LANE|LN|COURT|CT|WAY|PLACE|PL|HIGHWAY|HWY|TERRACE|TER|"
    r"CIRCLE|CIR|PARKWAY|PKWY)\b",
    re.IGNORECASE,
)
LICENSE_PLATE_PATTERN = re.compile(
    r"\b(?:license\s*plate|plate|lic(?:ense)?|tag)"
    r"(?:\s*(?:number|no\.?|#))?\s*[:#=-]?\s*(?:is\s+)?"
    r"(?=[A-Z0-9-]{3,9}\b)(?=[A-Z0-9-]*\d)"
    r"[A-Z0-9][A-Z0-9-]{2,8}\b",
    re.IGNORECASE,
)
WORD_PATTERN = r"\b[\w'-]+\b"
PLACEHOLDER_PATTERN = re.compile(
    r"\[(?:EMAIL|URL|PHONE|ADDRESS|LICENSE_PLATE)\]", re.IGNORECASE
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    return parser.parse_args()


def normalize_text(series: pd.Series) -> pd.Series:
    """Normalize Unicode and whitespace without removing linguistic context."""
    return (
        series.fillna("")
        .astype("string")
        .str.normalize("NFKC")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def sanitize_text(series: pd.Series) -> pd.Series:
    """Mask common identifiers before descriptions are sent to an API."""
    sanitized = series
    # Masking one identifier can expose a boundary for another (for example, a
    # phone number placed directly before a URL). A second pass catches those
    # newly exposed patterns.
    for _ in range(2):
        sanitized = (
            sanitized.str.replace(EMAIL_PATTERN, "[EMAIL]", regex=True)
            .str.replace(URL_PATTERN, "[URL]", regex=True)
            .str.replace(PHONE_PATTERN, "[PHONE]", regex=True)
            .str.replace(ADDRESS_PATTERN, "[ADDRESS]", regex=True)
            .str.replace(LICENSE_PLATE_PATTERN, "[LICENSE_PLATE]", regex=True)
        )
    return sanitized.str.replace(r"\s+", " ", regex=True).str.strip()


def mask_known_street_addresses(
    descriptions: pd.Series, street_addresses: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """Mask an exact source street address before applying generic patterns."""
    normalized_addresses = normalize_text(street_addresses)
    masked_values: list[str] = []
    match_flags: list[bool] = []

    for description, address in zip(descriptions, normalized_addresses):
        should_mask = len(address) >= 6 and address.casefold() in description.casefold()
        if should_mask:
            description = re.sub(
                re.escape(address), "[ADDRESS]", description, flags=re.IGNORECASE
            )
        masked_values.append(description)
        match_flags.append(should_mask)

    return (
        pd.Series(masked_values, index=descriptions.index, dtype="string"),
        pd.Series(match_flags, index=descriptions.index, dtype="bool"),
    )


def has_semantic_text(series: pd.Series) -> pd.Series:
    """Return whether sanitized text contains content beyond placeholders/punctuation."""
    without_placeholders = series.str.replace(
        PLACEHOLDER_PATTERN, " ", regex=True
    )
    return without_placeholders.str.contains(r"[\w]", regex=True, na=False)


def metric_row(metric: str, value: object, notes: str = "") -> dict[str, object]:
    return {"metric": metric, "value": value, "notes": notes}


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(
            f"Raw dataset not found: {args.input}. See data/README.md for instructions."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.table_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input, dtype=STRING_COLUMNS, low_memory=False)
    missing_columns = sorted(EXPECTED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Raw dataset is missing required columns: {missing_columns}")

    if df["service_request_id"].duplicated().any():
        raise ValueError("service_request_id is not unique in the raw dataset")

    for column in ("date_requested", "date_closed"):
        df[column] = pd.to_datetime(df[column], errors="coerce")

    df["service_name"] = df["service_name"].str.strip()
    original_text = normalize_text(df["public_description"])
    text_without_source_address, has_source_street_address = (
        mask_known_street_addresses(original_text, df["street_address"])
    )
    clean_text = sanitize_text(text_without_source_address)
    description_key = clean_text.str.casefold()
    has_email = clean_text.str.contains(r"\[EMAIL\]", regex=True, na=False)
    has_url = clean_text.str.contains(r"\[URL\]", regex=True, na=False)
    has_phone = clean_text.str.contains(r"\[PHONE\]", regex=True, na=False)
    has_address = clean_text.str.contains(r"\[ADDRESS\]", regex=True, na=False)
    has_license_plate = clean_text.str.contains(
        r"\[LICENSE_PLATE\]", regex=True, na=False
    )

    residual_identifier_patterns = {
        "email": EMAIL_PATTERN,
        "URL": URL_PATTERN,
        "phone": PHONE_PATTERN,
        "street address": ADDRESS_PATTERN,
        "license plate": LICENSE_PLATE_PATTERN,
    }
    for label, pattern in residual_identifier_patterns.items():
        if clean_text.str.contains(pattern, regex=True, na=False).any():
            raise ValueError(f"Sanitization left at least one {label} pattern")

    has_description = original_text.ne("")
    has_semantic_description = has_semantic_text(clean_text)
    has_service_name = df["service_name"].notna() & df["service_name"].ne("")
    has_parent_request = normalize_text(df["service_request_parent_id"]).ne("")
    eligible = has_description & has_semantic_description & has_service_name

    eligible_keys = description_key[eligible]
    occurrence_count = eligible_keys.map(eligible_keys.value_counts())
    label_count = eligible_keys.map(
        df.loc[eligible].groupby(description_key[eligible])["service_name"].nunique()
    )
    group_codes, _ = pd.factorize(eligible_keys, sort=True)

    calculated_closure_days = (
        df["date_closed"].dt.normalize() - df["date_requested"].dt.normalize()
    ).dt.days.astype("Int64")
    case_age_days = pd.to_numeric(df["case_age_days"], errors="coerce").astype("Int64")

    prepared = df.loc[eligible].copy()
    prepared["public_description_clean"] = clean_text[eligible]
    prepared["description_character_count"] = clean_text[eligible].str.len().astype("Int64")
    prepared["description_word_count"] = (
        clean_text[eligible].str.count(WORD_PATTERN).astype("Int64")
    )
    prepared["description_group_id"] = pd.Series(
        group_codes + 1, index=prepared.index, dtype="Int64"
    )
    prepared["description_occurrence_count"] = occurrence_count.astype("Int64")
    prepared["description_label_count"] = label_count.astype("Int64")
    prepared["is_repeated_description"] = occurrence_count.gt(1)
    prepared["is_ambiguous_description"] = label_count.gt(1)
    prepared["has_parent_request"] = has_parent_request[eligible]
    prepared["contains_email"] = has_email[eligible]
    prepared["contains_url"] = has_url[eligible]
    prepared["contains_phone"] = has_phone[eligible]
    prepared["contains_address_pattern"] = has_address[eligible]
    prepared["contains_source_street_address"] = has_source_street_address[eligible]
    prepared["contains_license_plate_pattern"] = has_license_plate[eligible]
    prepared["contains_potential_identifier"] = (
        has_email[eligible]
        | has_url[eligible]
        | has_phone[eligible]
        | has_address[eligible]
        | has_license_plate[eligible]
    )
    prepared["request_year"] = prepared["date_requested"].dt.year.astype("Int64")
    prepared["request_month"] = prepared["date_requested"].dt.to_period("M").astype("string")
    prepared["request_day_of_week"] = prepared["date_requested"].dt.day_name()
    prepared["calculated_closure_days"] = calculated_closure_days[eligible]
    prepared["case_age_difference"] = (
        case_age_days[eligible] - calculated_closure_days[eligible]
    ).astype("Int64")
    prepared["has_invalid_chronology"] = calculated_closure_days[eligible].lt(0)

    output_columns = [
        "service_request_id",
        "service_request_parent_id",
        "date_requested",
        "date_closed",
        "case_age_days",
        "calculated_closure_days",
        "case_age_difference",
        "has_invalid_chronology",
        "case_record_type",
        "service_name",
        "service_name_detail",
        "status",
        "lat",
        "lng",
        "zipcode",
        "council_district",
        "comm_plan_name",
        "case_origin",
        "public_description_clean",
        "description_character_count",
        "description_word_count",
        "description_group_id",
        "description_occurrence_count",
        "description_label_count",
        "is_repeated_description",
        "is_ambiguous_description",
        "has_parent_request",
        "contains_email",
        "contains_url",
        "contains_phone",
        "contains_address_pattern",
        "contains_source_street_address",
        "contains_license_plate_pattern",
        "contains_potential_identifier",
        "request_year",
        "request_month",
        "request_day_of_week",
    ]
    prepared = prepared[output_columns]
    prepared.to_csv(args.output, index=False, compression="gzip")

    missingness = pd.DataFrame(
        {
            "column": df.columns,
            "missing_count": [int(df[column].isna().sum()) for column in df.columns],
        }
    )
    missingness["missing_share"] = missingness["missing_count"] / len(df)
    missingness.to_csv(args.table_dir / "missingness_summary.csv", index=False)

    category_counts = (
        prepared["service_name"]
        .value_counts()
        .rename_axis("service_name")
        .reset_index(name="eligible_count")
    )
    no_parent_counts = prepared.loc[~prepared["has_parent_request"], "service_name"].value_counts()
    category_counts["eligible_share"] = category_counts["eligible_count"] / len(prepared)
    category_counts["no_parent_count"] = (
        category_counts["service_name"].map(no_parent_counts).fillna(0).astype(int)
    )
    category_counts.to_csv(args.table_dir / "category_counts.csv", index=False)

    ambiguous_groups = int(
        prepared.loc[prepared["is_ambiguous_description"], "description_group_id"].nunique()
    )
    quality_rows = [
        metric_row("source_rows", len(df)),
        metric_row("source_columns", len(df.columns)),
        metric_row("unique_request_ids", int(df["service_request_id"].nunique())),
        metric_row("missing_service_name_rows", int((~has_service_name).sum())),
        metric_row("missing_or_blank_description_rows", int((~has_description).sum())),
        metric_row(
            "nonsemantic_description_rows",
            int((has_description & ~has_semantic_description).sum()),
            "Nonblank descriptions containing only placeholders or punctuation",
        ),
        metric_row("modeling_eligible_rows", len(prepared)),
        metric_row("raw_service_categories", int(df["service_name"].nunique(dropna=True))),
        metric_row("eligible_service_categories", int(prepared["service_name"].nunique())),
        metric_row("parent_child_rows", int(has_parent_request.sum())),
        metric_row("eligible_parent_child_rows", int(prepared["has_parent_request"].sum())),
        metric_row("repeated_description_rows", int(prepared["is_repeated_description"].sum())),
        metric_row("unique_eligible_descriptions", int(prepared["description_group_id"].nunique())),
        metric_row("ambiguous_description_groups", ambiguous_groups),
        metric_row("rows_with_ambiguous_description", int(prepared["is_ambiguous_description"].sum())),
        metric_row("descriptions_with_email", int(prepared["contains_email"].sum())),
        metric_row("descriptions_with_url", int(prepared["contains_url"].sum())),
        metric_row("descriptions_with_phone", int(prepared["contains_phone"].sum())),
        metric_row("descriptions_with_address_pattern", int(prepared["contains_address_pattern"].sum())),
        metric_row(
            "descriptions_with_source_street_address",
            int(prepared["contains_source_street_address"].sum()),
        ),
        metric_row(
            "descriptions_with_license_plate_pattern",
            int(prepared["contains_license_plate_pattern"].sum()),
        ),
        metric_row("invalid_chronology_rows", int(prepared["has_invalid_chronology"].sum())),
        metric_row("requests_submitted_before_2025", int((df["date_requested"] < pd.Timestamp("2025-01-01")).sum())),
        metric_row("requests_submitted_after_2025", int((df["date_requested"] >= pd.Timestamp("2026-01-01")).sum())),
        metric_row("minimum_request_date", df["date_requested"].min().isoformat()),
        metric_row("maximum_request_date", df["date_requested"].max().isoformat()),
        metric_row("minimum_close_date", df["date_closed"].min().date().isoformat()),
        metric_row("maximum_close_date", df["date_closed"].max().date().isoformat()),
    ]
    pd.DataFrame(quality_rows).to_csv(
        args.table_dir / "data_quality_summary.csv", index=False
    )

    print(f"Prepared {len(prepared):,} eligible rows from {len(df):,} source rows.")
    print(f"Wrote {args.output}")
    print(f"Wrote summary tables to {args.table_dir}")


if __name__ == "__main__":
    main()
