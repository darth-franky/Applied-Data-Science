# Predicting Early Hospital Readmission in Diabetic Patients — ADS 503 Final Project

**Course:** ADS 503 — Applied Predictive Modeling (University of San Diego, MS-ADS)
**Team:** Group 1
**Language:** R (Quarto / R Markdown)

## Problem Statement

Hospitals are penalized under CMS programs for patients readmitted within 30 days
of discharge. Using demographic, admission, diagnosis, and treatment information
captured during a hospital stay, we frame a **binary classification** problem:
*will a diabetic patient be readmitted within 30 days of discharge?* Accurate
prediction lets care teams target follow-up resources at the highest-risk patients.

## Dataset

[UCI — Diabetes 130-US Hospitals (1999–2008)](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008)

| | |
|---|---|
| **Encounters** (`datasets/diabetic_data.csv`) | 101,766 |
| **Unique patients** | 71,518 |
| **Predictors** | 50 columns (demographics, admission/discharge codes, diagnoses, lab results, 20+ medications) |
| **Target** | `readmitted` — `<30`, `>30`, `NO`; binarized to early (**<30 day**) readmission vs. not |
| **Class balance** | ~9% positive after cleaning (imbalanced) |
| **Missingness** | Coded as `?`; heaviest in `weight` (~97%), `medical_specialty` (~49%), `payer_code` (~40%) |

## Approach

1. **EDA** — target distribution, missingness review, and response-vs-predictor
   relationships (age, time in hospital, inpatient visits).
2. **Data wrangling & pre-processing**
   - Keep **one (first) encounter per patient** to prevent patient-level leakage.
   - Remove encounters discharged to **death/hospice** (cannot be readmitted).
   - Drop high-missingness/administrative columns (`weight`, `payer_code`,
     `medical_specialty`) and identifiers; retain missing `race` as `"Unknown"`.
   - Group 700+ raw **ICD-9 diagnosis codes** (`diag_1/2/3`) into clinical categories.
   - Binarize the target; remove **near-zero-variance** drug columns; check
     correlated numeric predictors.
3. **Data splitting** — stratified **60/20/20** train/validation/test (preserves
   the ~9% readmission rate in each set).
4. **Model strategy** — class imbalance handled via in-fold down-sampling;
   **ROC-AUC** as the primary metric, with sensitivity, specificity, balanced
   accuracy, and F1.
5. **Model building & results** — logistic, penalized logistic (glmnet), MARS,
   CART, random forest, and gradient boosting, tuned via 5-fold CV. *(In progress.)*

## Repository Structure

```
.
├── ADS_503_diabetes_final.qmd   # Main analysis notebook (EDA → pre-processing → splitting → strategy)
├── README.md
└── datasets/
    ├── diabetic_data.csv        # UCI diabetes dataset (101,766 encounters)
    └── description.pdf          # Dataset documentation / data dictionary
```

## How to Run

Requires **R (≥ 4.5)** and **Quarto**. Install the packages used in the notebook:

```r
install.packages(c("tidyverse", "caret"))
# Model-building stage additionally uses:
# install.packages(c("glmnet", "earth", "ranger", "gbm", "pROC"))
```

Then render the report:

```bash
quarto render ADS_503_diabetes_final.qmd --to html
```

## Status & Division of Work

| Area | Status | Owner |
|---|---|---|
| EDA | Complete | *Brianna Sanchez* |
| Data wrangling & pre-processing | Complete | *Franky Hernandez* |
| Data splitting | Complete | *Franky Hernandez* |
| Model strategy | Complete | *Franky Hernandez* |
| Model building, validation & results | In progress | *Franky Hernandez / Daniel Lopez* |
| Technical report & executive summary | Pending | Team |

## Notes

- The project originally explored a car-insurance claims dataset but **pivoted to
  this life-sciences dataset** per course requirements.
- `readmitted` is binarized to **`<30` vs. all else**, targeting clinically
  actionable early readmission.
