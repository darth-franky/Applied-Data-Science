"""Shared readers that preserve logical types in project data files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_PREPARED_DATA = Path(
    "data/processed/get_it_done_requests_closed_2025_prepared.csv.gz"
)

PREPARED_DTYPES = {
    "service_request_id": "string",
    "service_request_parent_id": "string",
    "case_age_days": "Int64",
    "calculated_closure_days": "Int64",
    "case_age_difference": "Int64",
    "has_invalid_chronology": "boolean",
    "case_record_type": "string",
    "service_name": "string",
    "service_name_detail": "string",
    "status": "string",
    "zipcode": "string",
    "council_district": "string",
    "comm_plan_name": "string",
    "case_origin": "string",
    "public_description_clean": "string",
    "description_character_count": "Int64",
    "description_word_count": "Int64",
    "description_group_id": "Int64",
    "description_occurrence_count": "Int64",
    "description_label_count": "Int64",
    "is_repeated_description": "boolean",
    "is_ambiguous_description": "boolean",
    "has_parent_request": "boolean",
    "contains_email": "boolean",
    "contains_url": "boolean",
    "contains_phone": "boolean",
    "contains_address_pattern": "boolean",
    "contains_source_street_address": "boolean",
    "contains_license_plate_pattern": "boolean",
    "contains_potential_identifier": "boolean",
    "request_year": "Int64",
    "request_month": "string",
    "request_day_of_week": "string",
}


def load_prepared_data(path: Path = DEFAULT_PREPARED_DATA) -> pd.DataFrame:
    """Load the prepared CSV while retaining IDs, codes, dates, and booleans."""
    return pd.read_csv(
        path,
        dtype=PREPARED_DTYPES,
        parse_dates=["date_requested", "date_closed"],
        low_memory=False,
    )
