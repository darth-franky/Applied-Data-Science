# ADS 509 Final Project

## Project direction

This project follows **Option 2 — Generative AI Application**. It evaluates whether a generative AI model accessed through an API can classify City of San Diego Get It Done service-request descriptions into the city's existing service categories.

### Working research question

> How accurately can a generative AI model classify the public descriptions of San Diego Get It Done requests into the city's existing service categories?

The model input is the sanitized `public_description_clean`. The reference label is `service_name`. The project will compare the API predictions with a traditional text-classification baseline using the same evaluation observations.

## Dataset

The project uses **Get It Done Requests closed in 2025** from the City of San Diego Open Data Portal. The raw CSV is not stored in Git because it is approximately 128 MB and exceeds GitHub's file-size limit.

See [`data/README.md`](data/README.md) for download and placement instructions.

## Current repository workflow

1. Download the raw CSV into `data/raw/`.
2. Run the preparation script to validate, sanitize, and derive modeling fields.
3. Run the EDA script to create summary tables, figures, and a data-quality report.
4. Run the unit tests for the highest-risk text transformations.

```bash
python src/prepare_data.py
python src/run_eda.py
python -m unittest discover -s tests
```

The scripts default to these paths:

```text
data/raw/get_it_done_requests_closed_2025_datasd.csv
data/processed/get_it_done_requests_closed_2025_prepared.csv.gz
outputs/tables/
outputs/figures/
outputs/data_quality_summary.md
```

## Data-preparation principles

- Preserve the full source population for descriptive analysis.
- Exclude rows without both a usable description and service category from the modeling dataset.
- Retain duplicate and parent-request indicators instead of silently deleting records.
- Mask common email, URL, phone-number, and street-address patterns in the API-ready description.
- Mask an exact source street address when it is repeated in the public description.
- Group identical sanitized model inputs together to prevent train/test leakage.
- Exclude the source `street_address` field from the prepared modeling file.
- Keep the true `service_name` outside prompts and use it only for evaluation.

Pattern-based masking is a risk reduction step, not a guarantee of anonymity. The
final API sample still requires a manual privacy review, especially for personal
names, unit numbers, and unusual license-plate formats.

The current EDA uses aggregated council-district counts. Validate and filter
coordinate outliers before creating any future request-level point map, and do
not include request coordinates in API prompts.

Downstream scripts should use `load_prepared_data()` from `src/data_io.py` so
request IDs, ZIP codes, council districts, dates, and Boolean fields retain their
intended types.

## Reproducibility

Install the current data-preparation dependencies with:

```bash
python -m pip install -r requirements.txt
```

API credentials must be stored in a local `.env` file and must never be committed.
