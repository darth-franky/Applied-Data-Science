"""
run_pipeline.py — Headless OULAD ELT pipeline.

Runs the full Extract → Load → Transform → Monitor sequence without a
Jupyter kernel.  Called by trigger_watcher.py (event-based) and by CI.

Usage:
    python src/run_pipeline.py

Environment variables (set in .env or shell):
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("oulad_pipeline")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent
DATA_DIR   = ROOT / "open+university+learning+analytics+dataset"
OUTPUTS    = ROOT / "outputs"
LOG_FILE   = OUTPUTS / "pipeline_run.log"
OUTPUTS.mkdir(exist_ok=True)

NA_VALUES  = ["?", ""]
CHUNK_SIZE = 500_000

RAW_FILES = {
    "courses":              "courses.csv",
    "assessments":          "assessments.csv",
    "vle":                  "vle.csv",
    "student_info":         "studentInfo.csv",
    "student_registration": "studentRegistration.csv",
    "student_assessment":   "studentAssessment.csv",
}

DDL = """
DROP TABLE IF EXISTS student_vle;
DROP TABLE IF EXISTS student_assessment;
DROP TABLE IF EXISTS student_registration;
DROP TABLE IF EXISTS student_info;
DROP TABLE IF EXISTS vle;
DROP TABLE IF EXISTS assessments;
DROP TABLE IF EXISTS courses;

CREATE TABLE courses (
    code_module                VARCHAR(10) NOT NULL,
    code_presentation          VARCHAR(10) NOT NULL,
    module_presentation_length INT,
    PRIMARY KEY (code_module, code_presentation)
);
CREATE TABLE assessments (
    id_assessment     INT PRIMARY KEY,
    code_module       VARCHAR(10),
    code_presentation VARCHAR(10),
    assessment_type   VARCHAR(20),
    date              INT,
    weight            FLOAT
);
CREATE TABLE vle (
    id_site           INT PRIMARY KEY,
    code_module       VARCHAR(10),
    code_presentation VARCHAR(10),
    activity_type     VARCHAR(50),
    week_from         INT,
    week_to           INT
);
CREATE TABLE student_info (
    code_module          VARCHAR(10) NOT NULL,
    code_presentation    VARCHAR(10) NOT NULL,
    id_student           INT         NOT NULL,
    gender               VARCHAR(5),
    region               VARCHAR(100),
    highest_education    VARCHAR(100),
    imd_band             VARCHAR(20),
    age_band             VARCHAR(20),
    num_of_prev_attempts INT,
    studied_credits      INT,
    disability           VARCHAR(5),
    final_result         VARCHAR(20),
    PRIMARY KEY (code_module, code_presentation, id_student)
);
CREATE TABLE student_registration (
    code_module          VARCHAR(10) NOT NULL,
    code_presentation    VARCHAR(10) NOT NULL,
    id_student           INT         NOT NULL,
    date_registration    INT,
    date_unregistration  INT,
    PRIMARY KEY (code_module, code_presentation, id_student)
);
CREATE TABLE student_assessment (
    id_assessment  INT     NOT NULL,
    id_student     INT     NOT NULL,
    date_submitted INT,
    is_banked      TINYINT,
    score          FLOAT,
    PRIMARY KEY (id_assessment, id_student)
);
CREATE TABLE student_vle (
    code_module       VARCHAR(10),
    code_presentation VARCHAR(10),
    id_student        INT,
    id_site           INT,
    date              INT,
    sum_click         INT,
    INDEX idx_svle_student (code_module, code_presentation, id_student),
    INDEX idx_svle_date    (date)
);
"""

TRANSFORMS = [
    ("fact_weekly_engagement", """
        DROP TABLE IF EXISTS fact_weekly_engagement;
        CREATE TABLE fact_weekly_engagement AS
        SELECT
            code_module,
            code_presentation,
            id_student,
            FLOOR(date / 7)  AS week_num,
            SUM(sum_click)   AS total_clicks,
            COUNT(*)         AS n_events
        FROM student_vle
        GROUP BY code_module, code_presentation, id_student, FLOOR(date / 7)
    """),
    ("engagement_with_outcomes", """
        DROP TABLE IF EXISTS engagement_with_outcomes;
        CREATE TABLE engagement_with_outcomes AS
        SELECT
            e.code_module,
            e.code_presentation,
            e.id_student,
            e.week_num,
            e.total_clicks,
            e.n_events,
            s.final_result
        FROM fact_weekly_engagement e
        JOIN student_info s
          ON  e.id_student       = s.id_student
          AND e.code_module      = s.code_module
          AND e.code_presentation = s.code_presentation
    """),
    ("early_risk_flags", """
        DROP TABLE IF EXISTS early_risk_flags;
        CREATE TABLE early_risk_flags AS
        SELECT
            code_module,
            code_presentation,
            id_student,
            SUM(total_clicks) AS clicks_weeks_0_2,
            MAX(final_result) AS final_result,
            CASE WHEN SUM(total_clicks) < 50 THEN 1 ELSE 0 END AS low_engagement_flag
        FROM engagement_with_outcomes
        WHERE week_num BETWEEN 0 AND 2
        GROUP BY code_module, code_presentation, id_student
    """),
    ("instructor_review_queue", """
        DROP TABLE IF EXISTS instructor_review_queue;
        CREATE TABLE instructor_review_queue AS
        SELECT
            code_module,
            code_presentation,
            id_student,
            clicks_weeks_0_2,
            final_result,
            low_engagement_flag,
            RANK() OVER (
                PARTITION BY code_module, code_presentation
                ORDER BY clicks_weeks_0_2 ASC
            ) AS engagement_rank
        FROM early_risk_flags
    """),
]


def build_engine():
    load_dotenv(ROOT / ".env")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    pw   = os.getenv("DB_PASSWORD", "")
    name = os.getenv("DB_NAME", "oulad_db")

    base = create_engine(f"mysql+mysqlconnector://{user}:{pw}@{host}:{port}")
    with base.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{name}`"))
    return create_engine(f"mysql+mysqlconnector://{user}:{pw}@{host}:{port}/{name}")


def run_sql_block(engine, sql_block):
    with engine.begin() as conn:
        for stmt in sql_block.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))


def extract():
    log.info("EXTRACT — loading CSVs")
    frames = {}
    for name, fname in RAW_FILES.items():
        path = DATA_DIR / fname
        frames[name] = pd.read_csv(path, na_values=NA_VALUES, low_memory=False)
        log.info("  %-25s %10s rows", name, f"{len(frames[name]):,}")
    return frames


def load(engine, frames):
    log.info("LOAD — writing raw tables to MySQL")
    run_sql_block(engine, DDL)
    log.info("  DDL applied — tables (re)created")

    for name, df in frames.items():
        df.to_sql(name, engine, if_exists="append", index=False)
        log.info("  Loaded %-25s %10s rows", name, f"{len(df):,}")

    log.info("  Loading student_vle in %s-row chunks (simulating incremental feed)",
             f"{CHUNK_SIZE:,}")
    total = 0
    for i, chunk in enumerate(
        pd.read_csv(
            DATA_DIR / "studentVle.csv",
            chunksize=CHUNK_SIZE,
            na_values=NA_VALUES,
            low_memory=False,
        )
    ):
        chunk.columns = ["code_module", "code_presentation",
                         "id_student", "id_site", "date", "sum_click"]
        chunk.to_sql("student_vle", engine, if_exists="append", index=False)
        total += len(chunk)
        log.info("    chunk %02d: %7s rows  (cumulative: %s)", i + 1,
                 f"{len(chunk):,}", f"{total:,}")

    log.info("  student_vle fully loaded: %s rows", f"{total:,}")


def transform(engine):
    log.info("TRANSFORM — running SQL transformations")
    for name, sql in TRANSFORMS:
        run_sql_block(engine, sql)
        n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {name}", engine).iloc[0, 0]
        log.info("  %-30s %10s rows", name, f"{n:,}")


def health_check(engine):
    log.info("MONITOR — running health checks")
    required = {
        "courses", "assessments", "vle",
        "student_info", "student_registration", "student_assessment", "student_vle",
        "fact_weekly_engagement", "engagement_with_outcomes",
        "early_risk_flags", "instructor_review_queue",
    }
    with engine.connect() as conn:
        existing = {r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()}
        missing = required - existing
        if missing:
            raise RuntimeError(f"Health check FAILED — missing tables: {missing}")

        for tbl in ["fact_weekly_engagement", "early_risk_flags", "instructor_review_queue"]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
            if n == 0:
                raise RuntimeError(f"Health check FAILED — {tbl} is empty")

        row = conn.execute(text("""
            SELECT
                SUM(id_student        IS NULL),
                SUM(code_module       IS NULL),
                SUM(code_presentation IS NULL)
            FROM instructor_review_queue
        """)).fetchone()
        if any(v > 0 for v in row):
            raise RuntimeError(f"Health check FAILED — NULL key fields: {row}")

        bad = conn.execute(text("""
            SELECT COUNT(*) FROM early_risk_flags
            WHERE low_engagement_flag NOT IN (0, 1)
        """)).scalar()
        if bad > 0:
            raise RuntimeError(f"Health check FAILED — {bad} invalid flag values")

    log.info("  All health checks PASSED")


def export_outputs(engine):
    log.info("EXPORT — writing output files")

    df_queue = pd.read_sql("""
        SELECT * FROM instructor_review_queue
        WHERE engagement_rank <= 5
        ORDER BY code_module, code_presentation, engagement_rank
    """, engine)
    p1 = OUTPUTS / "instructor_review_queue_top5_per_course.csv"
    df_queue.to_csv(p1, index=False)
    log.info("  Wrote %s (%s rows)", p1.name, f"{len(df_queue):,}")

    df_kpi = pd.read_sql("""
        SELECT
            COUNT(*)                                                           AS students_in_early_window,
            SUM(low_engagement_flag)                                           AS flagged_students,
            SUM(low_engagement_flag = 1 AND final_result IN ('Fail','Withdrawn')) AS flagged_and_at_risk
        FROM early_risk_flags
    """, engine)
    p2 = OUTPUTS / "pipeline_kpis.csv"
    df_kpi.to_csv(p2, index=False)
    log.info("  Wrote %s", p2.name)

    ts = datetime.now().isoformat(timespec="seconds")
    with open(LOG_FILE, "a") as f:
        f.write(f"\n=== RUN {ts} ===\n")
        for tbl in ["fact_weekly_engagement", "early_risk_flags", "instructor_review_queue"]:
            n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {tbl}", engine).iloc[0, 0]
            f.write(f"  {tbl:<32}: {n:,}\n")
        f.write("  health_checks: PASSED\n")
    log.info("  Appended run entry to %s", LOG_FILE.name)


def main():
    log.info("=" * 60)
    log.info("OULAD Pipeline starting")
    log.info("=" * 60)

    engine = build_engine()
    frames = extract()
    load(engine, frames)
    transform(engine)
    health_check(engine)
    export_outputs(engine)

    log.info("=" * 60)
    log.info("Pipeline complete — all stages passed")
    log.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.error("Pipeline FAILED: %s", exc)
        sys.exit(1)
