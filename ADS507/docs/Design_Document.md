# ADS-507 Final Project — Design Document

## OULAD Learning Analytics Pipeline

**GitHub Repository:** _[Applied Data Science - ADS507](https://github.com/darth-franky/Applied-Data-Science/tree/main/ADS507)_

**Team Members:** Francisco Hernandez, Ramin Fazil

**Course:** ADS-507 | University of San Diego | Applied Data Science

---

## 1. Source Dataset

### 1.1 What is the dataset?

The **Open University Learning Analytics Dataset (OULAD)** is a publicly available
research dataset published by The Open University (UK). It contains anonymized records
of student enrollment, engagement with a Virtual Learning Environment (VLE), and
assessment outcomes across seven undergraduate module-presentations spanning 2013–2014.

| File                      | Description                                           | Rows       |
| ------------------------- | ----------------------------------------------------- | ---------- |
| `courses.csv`             | Module-presentation catalog                           | 22         |
| `assessments.csv`         | Assessment metadata (type, due date, weight)          | 206        |
| `vle.csv`                 | VLE resource catalog (activity type, scheduled weeks) | 6,364      |
| `studentInfo.csv`         | Student demographics and final results                | 32,593     |
| `studentRegistration.csv` | Enrollment and withdrawal dates                       | 32,593     |
| `studentAssessment.csv`   | Per-student assessment scores and submission dates    | 173,912    |
| `studentVle.csv`          | Daily VLE click-stream logs                           | 10,655,280 |

**Total:** ~10.9 million records across 7 relational tables.

### 1.2 Where was it found?

The dataset was downloaded from the official OULAD repository:
[https://archive.ics.uci.edu/dataset/349/open+university+learning+analytics+dataset](https://archive.ics.uci.edu/dataset/349/open+university+learning+analytics+dataset)

It is published under the **Creative Commons Attribution 4.0** license and is
freely available for academic and research use.

### 1.3 Why did we choose it?

We selected OULAD for three reasons:

1. **Real-world complexity.** Seven relational tables with composite join keys, a
   10-million-row clickstream, and realistic data quality issues (missing values
   encoded as `?`) make it representative of a genuine production ELT challenge.

2. **Meaningful output.** Early identification of at-risk students is a documented,
   high-impact problem in higher education analytics. The dataset directly supports
   actionable instructor-facing output.

3. **Alignment with course requirements.** The relational structure demands SQL
   transformations, the scale exercises pipeline engineering concerns (chunked
   loading, indexing), and the static snapshot allows us to simulate an incremental
   data feed — satisfying the triggered-pipeline requirement.

---

## 2. Pipeline Architecture

### 2.1 Overview

The pipeline follows an **ELT** pattern: raw data is loaded into MySQL first,
then transformed entirely in SQL. This keeps transformation logic close to the
data and makes it easy to audit, version, and re-run.

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│   7 OULAD CSV files (SIS + LMS analog)                          │
│   assessments · courses · vle · studentInfo                     │
│   studentRegistration · studentAssessment · studentVle          │
└────────────────────────┬────────────────────────────────────────┘
                         │  Extract
                         │  pandas.read_csv()
                         │  na_values=['?']  (missing-value handling)
                         │  Key-field assertions (fail-fast validation)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LOAD — MySQL 8.0 (oulad_db)                  │
│                                                                  │
│  Small tables → single batch INSERT (SQLAlchemy + to_sql)       │
│  student_vle  → 500,000-row chunks (simulated incremental feed) │
│                                                                  │
│  RAW TABLES                                                      │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │   courses    │  │ assessments │  │        vle           │   │
│  └──────────────┘  └─────────────┘  └──────────────────────┘   │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │ student_info │  │  student_   │  │  student_assessment  │   │
│  │              │  │ registration│  │                      │   │
│  └──────────────┘  └─────────────┘  └──────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                     student_vle                         │    │
│  │  (10,655,280 rows — indexed on date + composite key)    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  TRANSFORM (SQL — DROP / CREATE TABLE AS SELECT)                 │
│  ┌──────────────────────────┐                                   │
│  │  fact_weekly_engagement  │  FLOOR(date/7) aggregation        │
│  └──────────┬───────────────┘                                   │
│             │ JOIN student_info (3-part composite key)          │
│  ┌──────────▼───────────────┐                                   │
│  │ engagement_with_outcomes │                                   │
│  └──────────┬───────────────┘                                   │
│             │ WHERE week_num BETWEEN 0 AND 2                    │
│  ┌──────────▼───────────────┐                                   │
│  │    early_risk_flags      │  low_engagement_flag (clicks < 50)│
│  └──────────┬───────────────┘                                   │
│             │ RANK() OVER (PARTITION BY module, presentation)   │
│  ┌──────────▼───────────────┐                                   │
│  │ instructor_review_queue  │                                   │
│  └──────────────────────────┘                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │  Monitor + Analyze
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                          OUTPUTS                                 │
│  instructor_review_queue_top5_per_course.csv                    │
│  pipeline_kpis.csv                                               │
│  engagement_by_outcome.png                                       │
│  pipeline_run.log                                                │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Component     | Technology                              | Rationale                                     |
| ------------- | --------------------------------------- | --------------------------------------------- |
| Orchestration | Jupyter Notebook                        | Reproducible, auditable, presentable          |
| Extract       | pandas 2.x                              | Handles 10M-row CSV with chunked reading      |
| Load          | SQLAlchemy 2.x + mysql-connector-python | ORM-agnostic; supports chunked `to_sql`       |
| Database      | MySQL 8.0                               | Required by course; supports window functions |
| Transform     | Native MySQL SQL                        | Keeps logic in the database; easy to version  |
| Testing       | pytest 7.x                              | Industry standard; separates unit/integration |
| CI            | GitHub Actions                          | Automatic testing on every push to `main`     |

---

## 3. Database Schema

### 3.1 Raw Tables (loaded from CSV)

```
courses
─────────────────────────────────────
PK  code_module          VARCHAR(10)
PK  code_presentation    VARCHAR(10)
    module_presentation_length  INT


assessments
─────────────────────────────────────
PK  id_assessment        INT
    code_module          VARCHAR(10)
    code_presentation    VARCHAR(10)
    assessment_type      VARCHAR(20)
    date                 INT
    weight               FLOAT


vle
─────────────────────────────────────
PK  id_site              INT
    code_module          VARCHAR(10)
    code_presentation    VARCHAR(10)
    activity_type        VARCHAR(50)
    week_from            INT  (nullable)
    week_to              INT  (nullable)


student_info
─────────────────────────────────────
PK  code_module          VARCHAR(10)
PK  code_presentation    VARCHAR(10)
PK  id_student           INT
    gender               VARCHAR(5)
    region               VARCHAR(100)
    highest_education    VARCHAR(100)
    imd_band             VARCHAR(20)
    age_band             VARCHAR(20)
    num_of_prev_attempts INT
    studied_credits      INT
    disability           VARCHAR(5)
    final_result         VARCHAR(20)


student_registration
─────────────────────────────────────
PK  code_module          VARCHAR(10)
PK  code_presentation    VARCHAR(10)
PK  id_student           INT
    date_registration    INT
    date_unregistration  INT  (nullable — NULL if not withdrawn)


student_assessment
─────────────────────────────────────
PK  id_assessment        INT
PK  id_student           INT
    date_submitted       INT
    is_banked            TINYINT
    score                FLOAT  (nullable)


student_vle
─────────────────────────────────────
    code_module          VARCHAR(10)
    code_presentation    VARCHAR(10)
    id_student           INT
    id_site              INT
    date                 INT
    sum_click            INT
IDX idx_svle_student (code_module, code_presentation, id_student)
IDX idx_svle_date   (date)
```

### 3.2 Transformed Tables (analytics layer)

```
fact_weekly_engagement
─────────────────────────────────────
    code_module          VARCHAR(10)
    code_presentation    VARCHAR(10)
    id_student           INT
    week_num             INT          ← FLOOR(date / 7)
    total_clicks         BIGINT       ← SUM(sum_click)
    n_events             BIGINT       ← COUNT(*)


engagement_with_outcomes
─────────────────────────────────────
    code_module          VARCHAR(10)
    code_presentation    VARCHAR(10)
    id_student           INT
    week_num             INT
    total_clicks         BIGINT
    n_events             BIGINT
    final_result         VARCHAR(20)  ← joined from student_info


early_risk_flags
─────────────────────────────────────
    code_module          VARCHAR(10)
    code_presentation    VARCHAR(10)
    id_student           INT
    clicks_weeks_0_2     DOUBLE       ← SUM of weeks 0–2
    final_result         VARCHAR(20)
    low_engagement_flag  INT          ← 1 if clicks_weeks_0_2 < 50


instructor_review_queue
─────────────────────────────────────
    code_module          VARCHAR(10)
    code_presentation    VARCHAR(10)
    id_student           INT
    clicks_weeks_0_2     DOUBLE
    final_result         VARCHAR(20)
    low_engagement_flag  INT
    engagement_rank      BIGINT       ← RANK() OVER (PARTITION BY module, presentation)
```

### 3.3 Entity-Relationship Summary

```
courses ──────────────────────────────────────────┐
    (code_module, code_presentation)               │
                                                   │
assessments ──────────────────────────────────────┤  composite
    (code_module, code_presentation, id_assessment)│  join key
                                                   │  used throughout
student_info ─────────────────────────────────────┤
    (code_module, code_presentation, id_student)   │
            │                                      │
student_registration                               │
    (code_module, code_presentation, id_student)   │
                                                   │
student_assessment                                 │
    (id_assessment, id_student) ───────────────────┘
            │
            └── id_assessment → assessments.id_assessment

student_vle
    (code_module, code_presentation, id_student, id_site, date)
            │
            └── id_site → vle.id_site
```

---

## 4. Pipeline Output

### 4.1 What does the pipeline produce?

| Output                                        | Description                                                                     |
| --------------------------------------------- | ------------------------------------------------------------------------------- |
| `instructor_review_queue_top5_per_course.csv` | Top 5 lowest-engagement students per module-presentation during weeks 0–2       |
| `pipeline_kpis.csv`                           | Summary: total students in early window, flagged count, flagged + at-risk count |
| `engagement_by_outcome.png`                   | Boxplot comparing early click totals for at-risk vs. not-at-risk students       |
| `pipeline_run.log`                            | Append-only timestamped log of every pipeline execution and health check result |

### 4.2 Why is the output useful?

**Early identification saves students.** Research on OULAD (Kuzilek et al., 2017) and
broader learning analytics literature establishes that VLE engagement in the first two
weeks of a course is the single strongest predictor of withdrawal. Students who click
fewer than 50 times during this window are substantially more likely to fail or withdraw
by end of term.

The **instructor review queue** translates this signal into an actionable list: support
staff receive the names of the lowest-engaging students within each course section,
ranked so the most at-risk are at the top. This enables targeted outreach — a phone call,
an email, or a referral to academic advising — before a student has fallen too far behind
to recover.

**Measured effectiveness:** The pipeline's low-engagement flag achieves approximately
63% precision (of flagged students, 63% ultimately fail or withdraw). This is high enough
to be useful for triage while acknowledging that some high-engagement students still
struggle (captured by recall). In a real deployment, precision and recall would be
monitored over time and the threshold adjusted accordingly.

---

## 5. Monitoring

The pipeline includes an automated `run_health_checks()` function that runs after
every transformation step. Checks include:

| Check                | What is verified                                                                         | Failure behavior      |
| -------------------- | ---------------------------------------------------------------------------------------- | --------------------- |
| Table existence      | All 11 expected tables are present in `oulad_db`                                         | `RuntimeError` raised |
| Row counts           | `fact_weekly_engagement`, `early_risk_flags`, `instructor_review_queue` are non-empty    | `RuntimeError` raised |
| NULL key fields      | `id_student`, `code_module`, `code_presentation` are fully populated in the review queue | `RuntimeError` raised |
| Flag column validity | `low_engagement_flag` contains only 0 or 1                                               | `RuntimeError` raised |

A timestamped entry is appended to `outputs/pipeline_run.log` on every successful run,
providing an audit trail for reproducibility review.

---

## 6. Continuous Integration

The repository is configured with **GitHub Actions** (`.github/workflows/ci.yml`).
On every push to `main` or pull request, the CI workflow:

1. Spins up a MySQL 8.0 service container
2. Installs all dependencies from `requirements.txt`
3. Runs `flake8` on the `tests/` directory (linter)
4. Runs all unit tests with `pytest -m "not integration"`

This ensures that logic errors in week binning, flag thresholds, and null handling
are caught before code is merged, without requiring a full dataset to be present in CI.

---

## 7. Gaps & System Assessment

### 7.1 Will the system scale as the dataset size grows?

**Current limitations:**

- `student_vle` at 10M rows loads in roughly 5–10 minutes on a single machine.
  At 100M rows this becomes impractical in a notebook.
- MySQL on a single host does not scale horizontally; large analytical queries
  will compete with write operations.

**Path to scale:**

- Replace the notebook orchestration with an **Apache Airflow** DAG so each
  chunk load becomes an atomic, retriable task.
- Migrate to a managed columnar store (e.g., **Amazon Redshift**, **Google BigQuery**)
  for the analytics layer, keeping MySQL only for operational writes.
- Add partitioning to `student_vle` on `date` to speed up the `WHERE week_num BETWEEN 0 AND 2` filter.

### 7.2 Is the system secure?

**Current state:**

- Database credentials are stored in `.env` (not committed to source control).
- `.env.example` provides a safe template; `.env` is in `.gitignore`.
- No hardcoded passwords anywhere in the notebook or source files.

**Gaps:**

- The pipeline connects as `root`. In production, a dedicated least-privilege
  MySQL user (`oulad_app`) with `SELECT`, `INSERT`, `CREATE TABLE` only should be used.
- Credentials are not rotated automatically. Production would use a secrets manager
  (AWS Secrets Manager, HashiCorp Vault) with short-lived tokens.
- The notebook itself is not encrypted; anyone with filesystem access can read the `.env`.

### 7.3 Is the system extensible?

**What is easy to extend:**

- **New data sources:** Add a new entry to `RAW_FILES` in Section 1 and a corresponding
  `CREATE TABLE` statement in the DDL block. The rest of the pipeline is unaffected.
- **New transformations:** Add a new `run_sql()` call in Section 3. The idempotent
  `DROP / CREATE` pattern means it integrates cleanly with existing tables.
- **New alert rules:** The `low_engagement_flag` threshold (50 clicks) is a single
  value in one SQL statement — straightforward to parameterize via a config file.
- **Predictive model:** The `early_risk_flags` table is structured to serve directly
  as a feature matrix for a logistic regression or gradient-boosted classifier.

**What requires more work:**

- Adding **real-time ingestion** would require replacing the CSV-based chunk simulation
  with a streaming consumer (Kafka, Kinesis) and a schema-on-read approach.
- A **multi-tenant** deployment (multiple institutions) would require schema-level
  isolation or row-level security policies not currently present.

---

## 8. Next Steps

1. Replace chunk-based simulation with a real incremental trigger (Airflow FileSensor or S3 event notification).
2. Add a logistic regression model trained on weeks 0–2 features to improve flag recall.
3. Connect `instructor_review_queue` to a Streamlit or Tableau dashboard for live instructor access.
4. Implement a dedicated `oulad_app` MySQL user with least-privilege permissions.
5. Add partition pruning to `student_vle` for faster week-range queries at scale.

---

## References

Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2015). Open University Learning Analytics dataset [[Dataset](https://archive.ics.uci.edu/static/public/349/open+university+learning+analytics+dataset.zip)]. UCI Machine Learning Repository. https://doi.org/10.24432/C5KK69.
