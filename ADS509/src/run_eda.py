"""Create initial EDA tables, figures, and a concise data-quality report."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from data_io import load_prepared_data


DEFAULT_DATA = Path(
    "data/processed/get_it_done_requests_closed_2025_prepared.csv.gz"
)
DEFAULT_TABLE_DIR = Path("outputs/tables")
DEFAULT_FIGURE_DIR = Path("outputs/figures")
DEFAULT_REPORT = Path("outputs/data_quality_summary.md")

COLOR = "#176B87"
ACCENT = "#D97706"
GRID = "#D9E2E8"
TEXT = "#172B3A"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def save_figure(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close()


def metric_lookup(summary: pd.DataFrame, metric: str) -> str:
    values = summary.loc[summary["metric"].eq(metric), "value"]
    if values.empty:
        raise KeyError(f"Missing metric in data-quality summary: {metric}")
    return str(values.iloc[0])


def integer_metric(summary: pd.DataFrame, metric: str) -> int:
    return int(float(metric_lookup(summary, metric)))


def main() -> None:
    args = parse_args()
    if not args.data.exists():
        raise FileNotFoundError(
            f"Prepared dataset not found: {args.data}. Run src/prepare_data.py first."
        )

    args.table_dir.mkdir(parents=True, exist_ok=True)
    args.figure_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    df = load_prepared_data(args.data)
    quality = pd.read_csv(args.table_dir / "data_quality_summary.csv", dtype="string")
    categories = pd.read_csv(args.table_dir / "category_counts.csv")

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 10,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT,
            "xtick.color": TEXT,
            "ytick.color": TEXT,
            "text.color": TEXT,
        }
    )

    top = categories.head(15).sort_values("eligible_count")
    plt.figure(figsize=(10, 7))
    bars = plt.barh(top["service_name"], top["eligible_count"], color=COLOR)
    plt.title("Most common service categories among usable descriptions", loc="left")
    plt.xlabel("Eligible requests")
    plt.grid(axis="x", color=GRID, linewidth=0.7, alpha=0.7)
    plt.gca().set_axisbelow(True)
    plt.bar_label(bars, labels=[f"{value:,.0f}" for value in top["eligible_count"]], padding=4, fontsize=8)
    plt.margins(x=0.12)
    save_figure(args.figure_dir / "top_service_categories.png")

    word_counts = df["description_word_count"].dropna()
    upper = int(word_counts.quantile(0.99))
    visible_word_counts = word_counts[word_counts <= upper]
    median = float(word_counts.median())
    plt.figure(figsize=(10, 5.5))
    plt.hist(visible_word_counts, bins=50, color=COLOR, edgecolor="white")
    plt.axvline(
        median,
        color=ACCENT,
        linewidth=2,
        linestyle="--",
        label=f"Median: {median:,.0f} words",
    )
    plt.title("Description length distribution", loc="left")
    plt.xlabel(
        f"Words per description (longest 1% above {upper} words not shown)"
    )
    plt.ylabel("Requests")
    plt.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.7)
    plt.gca().set_axisbelow(True)
    plt.legend(frameon=False)
    save_figure(args.figure_dir / "description_length_distribution.png")

    closed_by_month = (
        df.assign(close_month=df["date_closed"].dt.to_period("M").astype(str))
        .groupby("close_month")
        .size()
    )
    plt.figure(figsize=(10, 5.5))
    bars = plt.bar(closed_by_month.index, closed_by_month.values, color=COLOR)
    plt.title("Eligible requests closed or referred during 2025", loc="left")
    plt.xlabel("Closure month")
    plt.ylabel("Eligible requests")
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.7)
    plt.gca().set_axisbelow(True)
    plt.bar_label(bars, labels=[f"{value/1000:.1f}K" for value in closed_by_month.values], padding=3, fontsize=8)
    save_figure(args.figure_dir / "eligible_requests_by_close_month.png")

    geography_fields = {
        "lat": "Latitude",
        "lng": "Longitude",
        "zipcode": "ZIP code",
        "council_district": "Council district",
        "comm_plan_name": "Community planning area",
    }
    geography_rows = []
    for field, label in geography_fields.items():
        missing = df[field].isna()
        if isinstance(df[field].dtype, pd.StringDtype):
            missing = missing | df[field].str.strip().eq("")
        geography_rows.append(
            {
                "field": field,
                "label": label,
                "available_count": int((~missing).sum()),
                "missing_count": int(missing.sum()),
                "missing_share": float(missing.mean()),
            }
        )
    geography_coverage = pd.DataFrame(geography_rows)
    geography_coverage.to_csv(
        args.table_dir / "geography_coverage.csv", index=False
    )

    district_counts = (
        df["council_district"]
        .dropna()
        .str.strip()
        .loc[lambda values: values.ne("")]
        .value_counts()
        .rename_axis("council_district")
        .reset_index(name="eligible_count")
    )
    district_counts["eligible_share"] = district_counts["eligible_count"] / len(df)
    district_counts["sort_order"] = pd.to_numeric(
        district_counts["council_district"], errors="coerce"
    )
    district_counts = district_counts.sort_values(
        ["sort_order", "council_district"]
    ).drop(columns="sort_order")
    district_counts.to_csv(
        args.table_dir / "requests_by_council_district.csv", index=False
    )

    plt.figure(figsize=(10, 5.5))
    bars = plt.bar(
        district_counts["council_district"],
        district_counts["eligible_count"],
        color=COLOR,
    )
    plt.title("Eligible requests by council district", loc="left")
    plt.xlabel("Council district")
    plt.ylabel("Eligible requests")
    plt.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.7)
    plt.gca().set_axisbelow(True)
    plt.bar_label(
        bars,
        labels=[f"{value/1000:.1f}K" for value in district_counts["eligible_count"]],
        padding=3,
        fontsize=8,
    )
    save_figure(args.figure_dir / "eligible_requests_by_council_district.png")

    ranked = categories.sort_values("eligible_count", ascending=False).reset_index(drop=True)
    ranked["category_rank"] = ranked.index + 1
    ranked["cumulative_share"] = ranked["eligible_share"].cumsum()
    fig, left_axis = plt.subplots(figsize=(10, 5.5))
    left_axis.bar(ranked["category_rank"], ranked["eligible_count"], color=COLOR)
    left_axis.set_xlabel("Service-category rank")
    left_axis.set_ylabel("Eligible requests")
    left_axis.set_yscale("log")
    left_axis.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.7)
    left_axis.set_axisbelow(True)
    right_axis = left_axis.twinx()
    right_axis.plot(ranked["category_rank"], ranked["cumulative_share"], color=ACCENT, linewidth=2)
    right_axis.set_ylabel("Cumulative share")
    right_axis.set_ylim(0, 1.05)
    right_axis.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    left_axis.set_title("Category imbalance and cumulative coverage", loc="left")
    save_figure(args.figure_dir / "category_imbalance.png")

    text_summary = df["description_word_count"].describe(
        percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    )
    text_summary.rename_axis("statistic").reset_index(name="word_count").to_csv(
        args.table_dir / "text_length_summary.csv", index=False
    )

    duplicate_summary = pd.DataFrame(
        [
            {
                "measure": "Eligible parent-child requests",
                "count": int(df["has_parent_request"].sum()),
                "share": float(df["has_parent_request"].mean()),
            },
            {
                "measure": "Rows with repeated normalized descriptions",
                "count": int(df["is_repeated_description"].sum()),
                "share": float(df["is_repeated_description"].mean()),
            },
            {
                "measure": "Rows whose description maps to multiple categories",
                "count": int(df["is_ambiguous_description"].sum()),
                "share": float(df["is_ambiguous_description"].mean()),
            },
        ]
    )
    duplicate_summary.to_csv(args.table_dir / "duplicate_summary.csv", index=False)

    source_rows = integer_metric(quality, "source_rows")
    eligible_rows = integer_metric(quality, "modeling_eligible_rows")
    missing_descriptions = integer_metric(quality, "missing_or_blank_description_rows")
    raw_categories = integer_metric(quality, "raw_service_categories")
    eligible_categories = integer_metric(quality, "eligible_service_categories")
    parent_rows = integer_metric(quality, "eligible_parent_child_rows")
    repeated_rows = integer_metric(quality, "repeated_description_rows")
    ambiguous_groups = integer_metric(quality, "ambiguous_description_groups")
    ambiguous_rows = integer_metric(quality, "rows_with_ambiguous_description")
    invalid_chronology = integer_metric(quality, "invalid_chronology_rows")
    before_2025 = integer_metric(quality, "requests_submitted_before_2025")
    after_2025 = integer_metric(quality, "requests_submitted_after_2025")
    nonsemantic_descriptions = integer_metric(
        quality, "nonsemantic_description_rows"
    )

    top10_share = categories.head(10)["eligible_count"].sum() / eligible_rows
    categories_200 = int((categories["eligible_count"] >= 200).sum())
    short_descriptions = int((df["description_word_count"] <= 2).sum())
    council_missing = int(
        geography_coverage.loc[
            geography_coverage["field"].eq("council_district"), "missing_count"
        ].iloc[0]
    )
    largest_district = district_counts.loc[
        district_counts["eligible_count"].idxmax()
    ]

    report = f"""# Initial data-quality and EDA summary

## Scope

The source contains Get It Done requests closed or referred during 2025. It is a closure cohort, not a submission-year cohort. The request dates span `{metric_lookup(quality, 'minimum_request_date')}` through `{metric_lookup(quality, 'maximum_request_date')}`.

## Key findings

- The source contains **{source_rows:,} requests** and **{raw_categories} service categories**.
- **{eligible_rows:,} rows ({eligible_rows/source_rows:.1%})** contain both a usable `public_description` and `service_name` and are eligible for text classification.
- **{missing_descriptions:,} rows ({missing_descriptions/source_rows:.1%})** have a missing or blank description.
- **{nonsemantic_descriptions:,} additional nonblank rows** contain only punctuation or masked identifiers and are excluded from the modeling population.
- The eligible data contain **{eligible_categories} categories**. The 10 largest categories represent **{top10_share:.1%}** of eligible rows.
- **{categories_200} categories** have at least 200 eligible examples.
- **{short_descriptions:,} eligible descriptions ({short_descriptions/eligible_rows:.1%})** contain two words or fewer.
- **{parent_rows:,} eligible rows ({parent_rows/eligible_rows:.1%})** are linked to a parent request.
- **{repeated_rows:,} eligible rows ({repeated_rows/eligible_rows:.1%})** share their normalized description with at least one other request.
- **{ambiguous_groups:,} repeated description groups** map to more than one service category, affecting **{ambiguous_rows:,} rows ({ambiguous_rows/eligible_rows:.1%})**.
- **{before_2025:,} requests** were submitted before 2025 but closed during 2025. **{after_2025:,} request(s)** have a submission date in 2026 and require review.
- **{invalid_chronology:,} eligible row(s)** have a request date after the close date at day-level precision.
- Council district is available for **{eligible_rows-council_missing:,} eligible rows ({(eligible_rows-council_missing)/eligible_rows:.1%})**. District **{largest_district['council_district']}** has the largest eligible volume at **{int(largest_district['eligible_count']):,} requests**.

## Modeling implications

1. Rows without usable descriptions cannot support a text-only classifier and should remain outside the modeling population.
2. Identical normalized descriptions must remain in the same train/test group for the traditional baseline. Otherwise repeated text can leak across splits and inflate performance.
3. Parent-child requests should be excluded from the primary evaluation or tested in a separate sensitivity analysis.
4. Very short descriptions such as `graffiti` or `trash` can correspond to multiple operational categories. This creates an inherent limit for classification using `public_description` alone.
5. The team should choose the final category scope after reviewing `outputs/tables/category_counts.csv`. A defensible starting option is the {categories_200} categories with at least 200 eligible examples; a smaller top-category experiment would be easier to interpret but would narrow the research question.
6. API requests should use `public_description_clean`, not the original description or the separate street-address field.
7. Pattern masking reduces direct-identifier exposure but does not guarantee anonymization. Before API submission, the team should manually review the experiment sample for personal names, unit numbers, and unusual license-plate formats.
8. Geographic reporting should remain aggregated (for example, by council district); request-level coordinates should not be sent to the model.

## Generated artifacts

- `outputs/tables/data_quality_summary.csv`
- `outputs/tables/missingness_summary.csv`
- `outputs/tables/category_counts.csv`
- `outputs/tables/text_length_summary.csv`
- `outputs/tables/duplicate_summary.csv`
- `outputs/tables/geography_coverage.csv`
- `outputs/tables/requests_by_council_district.csv`
- `outputs/figures/top_service_categories.png`
- `outputs/figures/description_length_distribution.png`
- `outputs/figures/eligible_requests_by_close_month.png`
- `outputs/figures/eligible_requests_by_council_district.png`
- `outputs/figures/category_imbalance.png`
"""
    args.report.write_text(report, encoding="utf-8")

    print(f"Wrote EDA figures to {args.figure_dir}")
    print(f"Wrote EDA tables to {args.table_dir}")
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
