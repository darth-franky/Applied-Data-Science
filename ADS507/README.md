# ADS-507 Final Project: OULAD Production-Ready Learning Analytics Pipeline

## Overview
This repository contains a production-style ELT data pipeline built using the Open University Learning Analytics Dataset (OULAD).  
The pipeline loads raw SIS/LMS-style CSV data into a persistent DuckDB data store, transforms it into analytics-ready tables, and produces instructor-facing outputs to support early identification of at-risk students.

## Repository Contents
- `data/raw/`  
  Raw OULAD CSV files (input data). These files are not modified by the pipeline.
- `data/oulad.duckdb`  
  Persistent DuckDB database created/updated by the pipeline.
- `outputs/`  
  Generated outputs and monitoring logs:
  - `instructor_review_queue_top5_per_course.csv`
  - `pipeline_kpis.csv`
  - `pipeline_run.log`
- `src/`  
  (Optional) Source code folder for future refactors into scripts.
- `docs/`  
  Materials for the Design Document and architecture diagram.
- `dashboard/`  
  (Optional) Future dashboard deployment folder.

## How to Deploy / Run the Pipeline (Reproducible)
### Requirements
- Anaconda (conda)
- Python 3.11+
- Packages: `duckdb`, `pandas`, `pyarrow`, `matplotlib`, `jupyterlab`

### Setup
1. Create and activate the environment:
   - `conda create -n ads507 python=3.11 -y`
   - `conda activate ads507`
2. Install dependencies:
   - `pip install duckdb pandas pyarrow matplotlib jupyterlab`

### Run
1. Place the 7 OULAD CSV files in: `data/raw/`
2. Open the notebook:
   - `ads507_oulad_pipeline_run_from_scratch.ipynb`
3. Run:
   - Jupyter: **Kernel → Restart & Run All**

The pipeline will:
- Load raw tables into `data/oulad.duckdb`
- Build transformed tables:
  - `fact_weekly_engagement`
  - `engagement_with_outcomes`
  - `early_risk_flags`
  - `instructor_review_queue`
- Export outputs into `outputs/`

## How to Monitor the Pipeline
The notebook includes basic health checks. A successful run should show:
- `Missing tables: []`
- Null key checks equal to 0 for:
  - `id_student`, `code_module`, `code_presentation`
- Non-zero row counts for transformed tables
- An updated timestamp appended to:
  - `outputs/pipeline_run.log`

## Output Files
- `outputs/instructor_review_queue_top5_per_course.csv`  
  Top 5 lowest-engagement students per course presentation (weeks 0–2), intended for instructor/support review.
- `outputs/pipeline_kpis.csv`  
  Summary KPIs (students in early window, flagged count, flagged and at-risk count).
- `outputs/pipeline_run.log`  
  Append-only run log for monitoring and troubleshooting.

## Next Steps (Planned Enhancements)
- Replace rule-based flags with interpretable predictive models (e.g., logistic regression).
- Add additional features (assessment timing, submission patterns).
- Simulate/ingest live LMS/SIS data via APIs.
- Deploy a web dashboard for staff consumption.

