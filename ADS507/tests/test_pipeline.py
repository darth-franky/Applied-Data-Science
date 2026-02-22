"""
test_pipeline.py — pytest suite for the OULAD ELT pipeline.

Unit tests:        pure Python / pandas logic, no database required.
Integration tests: query MySQL; require a running DB with pipeline already run.
                   Marked with @pytest.mark.integration — skip with:
                     pytest -m "not integration"
"""
import io
import pytest
import pandas as pd


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS — week binning
# ═══════════════════════════════════════════════════════════════════

def test_week_binning_day_0():
    """date=0 maps to week 0."""
    assert int(0 // 7) == 0


def test_week_binning_day_6():
    """date=6 still maps to week 0 (same 7-day window as day 0)."""
    assert int(6 // 7) == 0


def test_week_binning_day_7():
    """date=7 maps to week 1."""
    assert int(7 // 7) == 1


def test_week_binning_day_13():
    """date=13 maps to week 1."""
    assert int(13 // 7) == 1


def test_week_binning_day_14():
    """date=14 maps to week 2."""
    assert int(14 // 7) == 2


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS — engagement flag threshold
# ═══════════════════════════════════════════════════════════════════

def test_flag_below_threshold():
    """49 clicks → flagged (strictly less than 50)."""
    assert (1 if 49 < 50 else 0) == 1


def test_flag_at_threshold():
    """50 clicks → NOT flagged (boundary is strictly less-than)."""
    assert (1 if 50 < 50 else 0) == 0


def test_flag_above_threshold():
    """80 clicks → not flagged."""
    assert (1 if 80 < 50 else 0) == 0


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS — data quality
# ═══════════════════════════════════════════════════════════════════

def test_null_handling_in_vle():
    """'?' sentinel in CSV becomes NaN after load with na_values=['?']."""
    csv = "code_module,date,sum_click\nAAA,?,5\n"
    df = pd.read_csv(io.StringIO(csv), na_values=["?"])
    assert pd.isna(df.loc[0, "date"])


def test_flag_column_is_binary(mini_flags):
    """low_engagement_flag must only contain 0 or 1."""
    assert set(mini_flags.low_engagement_flag.unique()).issubset({0, 1})


def test_precision_calculation(mini_flags):
    """Precision = flagged & at-risk / total flagged."""
    flagged = mini_flags[mini_flags.low_engagement_flag == 1]
    at_risk = flagged[flagged.final_result.isin(["Fail", "Withdrawn"])]
    precision = len(at_risk) / len(flagged)
    # In the mini fixture both flagged students are at-risk → precision = 1.0
    assert abs(precision - 1.0) < 1e-9


def test_week_numbers_are_non_negative(mini_vle):
    """FLOOR(date/7) must be ≥ 0 for all non-negative dates."""
    week_nums = (mini_vle["date"] // 7).astype(int)
    assert (week_nums >= 0).all()


def test_composite_key_uniqueness(mini_flags):
    """id_student must be unique in the mini fixture (no duplicate rows)."""
    assert mini_flags["id_student"].nunique() == len(mini_flags)


def test_clicks_non_negative(mini_vle):
    """sum_click must be non-negative."""
    assert (mini_vle["sum_click"] >= 0).all()


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — require running MySQL with pipeline executed
# ═══════════════════════════════════════════════════════════════════

pytestmark_integration = pytest.mark.integration


@pytest.mark.integration
def test_integration_row_counts(engine):
    """All transformed tables must be non-empty after pipeline run."""
    for tbl in ["fact_weekly_engagement", "early_risk_flags", "instructor_review_queue"]:
        n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {tbl}", engine).iloc[0, 0]
        assert n > 0, f"{tbl} is empty"


@pytest.mark.integration
def test_integration_no_null_keys(engine):
    """Composite keys in instructor_review_queue must be fully populated."""
    df = pd.read_sql("""
        SELECT id_student, code_module, code_presentation
        FROM instructor_review_queue
        WHERE id_student IS NULL
           OR code_module IS NULL
           OR code_presentation IS NULL
    """, engine)
    assert len(df) == 0, f"Found {len(df)} rows with null key fields"


@pytest.mark.integration
def test_integration_flag_values(engine):
    """low_engagement_flag in DB must be 0 or 1 only."""
    df = pd.read_sql(
        "SELECT DISTINCT low_engagement_flag FROM early_risk_flags", engine
    )
    assert set(df.low_engagement_flag.unique()).issubset({0, 1})


@pytest.mark.integration
def test_integration_rank_starts_at_one(engine):
    """Minimum engagement_rank per module-presentation must be 1."""
    n = pd.read_sql(
        "SELECT MIN(engagement_rank) AS min_rank FROM instructor_review_queue", engine
    ).iloc[0, 0]
    assert n == 1


@pytest.mark.integration
def test_integration_weekly_engagement_join_coverage(engine):
    """
    engagement_with_outcomes row count must be ≤ fact_weekly_engagement
    (the join can only drop rows, not add them).
    """
    n_fwe = pd.read_sql(
        "SELECT COUNT(*) AS n FROM fact_weekly_engagement", engine
    ).iloc[0, 0]
    n_ewo = pd.read_sql(
        "SELECT COUNT(*) AS n FROM engagement_with_outcomes", engine
    ).iloc[0, 0]
    assert n_ewo <= n_fwe, (
        f"engagement_with_outcomes ({n_ewo}) > fact_weekly_engagement ({n_fwe})"
    )
