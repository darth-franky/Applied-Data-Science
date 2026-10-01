# Dataset instructions

## Source

Dataset: **Get It Done Requests closed in 2025**  
Publisher: City of San Diego Performance & Analytics  
Dataset page: https://data.sandiego.gov/datasets/get-it-done-reports/  
Direct CSV: https://seshat.datasd.org/get_it_done_reports/get_it_done_requests_closed_2025_datasd.csv

## Source version used for this analysis

Verified locally on **2026-09-30**:

```text
File size: 128,229,965 bytes
SHA-256: b6c23e8d230eb867582c9d06f172558d72da73479e402fd394ef6d18058485d8
```

The city may revise the annual file. Teammates can verify that they are using the
same version with `shasum -a 256 data/raw/get_it_done_requests_closed_2025_datasd.csv`.

## Local placement

Download the file and save it as:

```text
data/raw/get_it_done_requests_closed_2025_datasd.csv
```

Both `data/raw/` and `data/processed/` are intentionally ignored by Git. Each teammate should download the official source locally and run the preparation script.

## Important cohort definition

This file contains requests **closed or referred during 2025**. It is not limited to requests submitted during 2025. The preparation and EDA workflows preserve the original request date so this distinction remains visible.

## Prepared output

Running `python src/prepare_data.py` creates:

```text
data/processed/get_it_done_requests_closed_2025_prepared.csv.gz
```

The prepared file contains eligible text-classification rows and derived quality flags. It omits the source street-address field and includes a sanitized `public_description_clean` field intended for downstream API experiments.
