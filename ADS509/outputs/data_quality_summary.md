# Initial data-quality and EDA summary

## Scope

The source contains Get It Done requests closed or referred during 2025. It is a closure cohort, not a submission-year cohort. The request dates span `2016-05-31T14:29:00` through `2026-03-01T11:14:00`.

## Key findings

- The source contains **378,669 requests** and **42 service categories**.
- **312,321 rows (82.5%)** contain both a usable `public_description` and `service_name` and are eligible for text classification.
- **66,260 rows (17.5%)** have a missing or blank description.
- **78 additional nonblank rows** contain only punctuation or masked identifiers and are excluded from the modeling population.
- The eligible data contain **41 categories**. The 10 largest categories represent **74.0%** of eligible rows.
- **34 categories** have at least 200 eligible examples.
- **42,859 eligible descriptions (13.7%)** contain two words or fewer.
- **41,763 eligible rows (13.4%)** are linked to a parent request.
- **83,479 eligible rows (26.7%)** share their normalized description with at least one other request.
- **2,882 repeated description groups** map to more than one service category, affecting **50,145 rows (16.1%)**.
- **26,732 requests** were submitted before 2025 but closed during 2025. **1 request(s)** have a submission date in 2026 and require review.
- **4 eligible row(s)** have a request date after the close date at day-level precision.
- Council district is available for **312,129 eligible rows (99.9%)**. District **3** has the largest eligible volume at **72,073 requests**.

## Modeling implications

1. Rows without usable descriptions cannot support a text-only classifier and should remain outside the modeling population.
2. Identical normalized descriptions must remain in the same train/test group for the traditional baseline. Otherwise repeated text can leak across splits and inflate performance.
3. Parent-child requests should be excluded from the primary evaluation or tested in a separate sensitivity analysis.
4. Very short descriptions such as `graffiti` or `trash` can correspond to multiple operational categories. This creates an inherent limit for classification using `public_description` alone.
5. The team should choose the final category scope after reviewing `outputs/tables/category_counts.csv`. A defensible starting option is the 34 categories with at least 200 eligible examples; a smaller top-category experiment would be easier to interpret but would narrow the research question.
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
