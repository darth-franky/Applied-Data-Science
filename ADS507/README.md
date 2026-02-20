# ADS-507 Final Project — OULAD Learning Analytics Pipeline

**University of San Diego | Applied Data Science**

---

## Repository Contents

| Path                                          | Description                                                                               |
| --------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `ads507_oulad_pipeline_1.ipynb`               | Main notebook — full ELT pipeline (Extract → Load → Transform → Monitor → Analyze → Test) |
| `open+university+learning+analytics+dataset/` | Raw OULAD CSV files (input data, not modified by pipeline)                                |
| `outputs/`                                    | Generated CSVs, chart, and run log                                                        |
| `tests/`                                      | pytest test suite (`test_pipeline.py`, `conftest.py`)                                     |
| `.github/workflows/ci.yml`                    | GitHub Actions CI — runs unit tests + linter on every push                                |
| `requirements.txt`                            | Python dependencies                                                                       |
| `.env.example`                                | Template for database credentials                                                         |
| `src/run_pipeline.py`                         | Headless pipeline script — runs full ELT without a notebook                               |
| `src/trigger_watcher.py`                      | Event-based trigger — watches data folder, fires pipeline on new/updated CSVs             |
| `docs/`                                       | Design document and architecture diagram                                                  |
| `dashboard/`                                  | Dashboard deployment folder                                                               |

---

## How to Deploy the Pipeline

### Prerequisites

- Python 3.10+
- **MySQL 8.0+** running locally or on a remote host
- conda or virtualenv (recommended: `NEWENV`)

### 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### 2 — Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in your MySQL host, user, password, and database name
```

### 3 — Create the MySQL schema

Log in to MySQL and run:

```sql
CREATE DATABASE IF NOT EXISTS oulad_db;
```

The pipeline will create all tables automatically on first run.

### 4 — Download the dataset

The raw data files are not included in this repository (`studentVle.csv` alone is 433 MB).
Download the dataset from UCI Machine Learning Repository:

**[https://archive.ics.uci.edu/dataset/349/open+university+learning+analytics+dataset](https://archive.ics.uci.edu/dataset/349/open+university+learning+analytics+dataset)**

Extract the zip and place all 7 CSV files here:

```
open+university+learning+analytics+dataset/
  assessments.csv
  courses.csv
  studentAssessment.csv
  studentInfo.csv
  studentRegistration.csv
  studentVle.csv
  vle.csv
```

### 5a — Run manually (notebook)

```bash
jupyter lab
```

Open `ads507_oulad_pipeline_1.ipynb` and select **Kernel → Restart & Run All**.

### 5b — Run headlessly (command line)

```bash
python src/run_pipeline.py
```

Runs the full ELT pipeline without a notebook. Same logic, same outputs, suitable for scripting and CI.

### 5c — Run automatically via event trigger

```bash
python src/trigger_watcher.py
```

Watches the data directory for new or modified CSV files. When a change is detected (e.g., a new data delivery), the pipeline runs automatically — no manual step needed. Stop with `Ctrl-C`.

**To simulate a triggered run:** with the watcher running, `touch` any CSV in the data folder:

```bash
touch "open+university+learning+analytics+dataset/studentVle.csv"
```

The watcher will detect the change and fire the pipeline within 5 seconds.

The pipeline will:

1. Extract all 7 CSV files and validate schemas
2. Load raw tables into MySQL (`student_vle` in 500 k-row chunks to simulate incremental ingestion)
3. Transform data into four analytics tables via SQL
4. Run health checks — raises `RuntimeError` if any check fails
5. Export outputs to `outputs/`

---

## How to Monitor the Pipeline

### Automated health checks

`run_health_checks()` (Section 4 of the notebook) verifies:

| Check                | Failure condition                                                                   |
| -------------------- | ----------------------------------------------------------------------------------- |
| Table existence      | Any of the 11 expected tables is missing                                            |
| Row counts           | `fact_weekly_engagement`, `early_risk_flags`, or `instructor_review_queue` is empty |
| NULL key fields      | Any NULL in `id_student`, `code_module`, or `code_presentation` in the review queue |
| Flag column validity | `low_engagement_flag` contains any value other than 0 or 1                          |

A failed check raises `RuntimeError` and stops the notebook immediately.

### Run log

Every successful run appends a timestamped entry to `outputs/pipeline_run.log`:

```
=== RUN 2026-02-18T14:32:01 ===
  fact_weekly_engagement  : 627,031
  early_risk_flags        : 27,544
  instructor_review_queue : 27,544
  health_checks           : PASSED
```

### Outputs

| File                                                  | Description                                                                    |
| ----------------------------------------------------- | ------------------------------------------------------------------------------ |
| `outputs/instructor_review_queue_top5_per_course.csv` | Top 5 lowest-engagement students per course/presentation for instructor review |
| `outputs/pipeline_kpis.csv`                           | Summary KPIs: total students, flagged count, flagged & at-risk count           |
| `outputs/engagement_by_outcome.png`                   | Boxplot of early engagement (weeks 0–2) by final outcome                       |
| `outputs/pipeline_run.log`                            | Append-only run log                                                            |

---

## Running Tests

```bash
# Unit tests only (no database required)
pytest tests/ -v -m "not integration"

# All tests (requires pipeline to have been run against MySQL)
pytest tests/ -v

# Lint check
flake8 tests/ --max-line-length=100
```

---

## Architecture

```
open+university+learning+analytics+dataset/
  (7 CSV files)
        │
        ▼  Extract (pandas, na_values=['?'])
  DataFrames
        │
        ▼  Load (SQLAlchemy + mysql-connector)
  MySQL 8.0 — oulad_db
  ┌─────────────────────────────────────────┐
  │  RAW TABLES                             │
  │  courses  assessments  vle              │
  │  student_info  student_registration     │
  │  student_assessment  student_vle        │
  │  (student_vle loaded in 500k chunks)    │
  │                                         │
  │  TRANSFORMED TABLES (SQL)               │
  │  fact_weekly_engagement                 │
  │  engagement_with_outcomes               │
  │  early_risk_flags                       │
  │  instructor_review_queue                │
  └─────────────────────────────────────────┘
        │
        ▼  Analyze + Export
  outputs/
  (CSVs, PNG chart, run log)
```

---

## Next Steps / Known Gaps

- **Scalability:** Single-node MySQL; production would use RDS or Cloud SQL with read replicas.
- **Real-time ingestion:** Chunk simulation would be replaced by an Airflow DAG + S3 event trigger or Kafka consumer.
- **Predictive model:** The 50-click threshold is a heuristic; logistic regression on weeks 0–2 features would improve recall.
- **Dashboard:** Connect the review queue to a live Streamlit or Tableau dashboard for instructors.
- **Security:** IAM-based credential rotation in production; no passwords in environment variables committed to source control.
