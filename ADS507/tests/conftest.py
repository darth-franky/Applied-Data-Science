"""
conftest.py — pytest fixtures for OULAD pipeline tests.

Integration tests use a real MySQL connection (credentials from .env or
environment variables).  Unit tests run entirely in memory with synthetic data.
"""
import os
import io
import pytest
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


# ── Engine fixture (integration tests only) ──────────────────────────────────
@pytest.fixture(scope="session")
def engine():
    host  = os.getenv("DB_HOST", "localhost")
    port  = os.getenv("DB_PORT", "3306")
    user  = os.getenv("DB_USER", "root")
    pw    = os.getenv("DB_PASSWORD", "")
    name  = os.getenv("DB_NAME", "oulad_db")
    url   = f"mysql+mysqlconnector://{user}:{pw}@{host}:{port}/{name}"
    eng   = create_engine(url)
    yield eng
    eng.dispose()


# ── Synthetic DataFrames (unit tests) ────────────────────────────────────────
@pytest.fixture
def mini_vle():
    return pd.DataFrame({
        "code_module":       ["AAA", "AAA", "AAA"],
        "code_presentation": ["2013J", "2013J", "2013J"],
        "id_student":        [1, 1, 2],
        "id_site":           [10, 10, 11],
        "date":              [0, 7, 0],
        "sum_click":         [30, 20, 10],
    })


@pytest.fixture
def mini_flags():
    return pd.DataFrame({
        "id_student":          [1,    2,    3,           4],
        "clicks_weeks_0_2":    [10.0, 80.0, 49.0,       50.0],
        "final_result":        ["Fail", "Pass", "Withdrawn", "Pass"],
        "low_engagement_flag": [1,    0,    1,           0],
    })
