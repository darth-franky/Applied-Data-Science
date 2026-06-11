# Predicting Car Insurance Claims — ADS 503 Final Project

**Course:** ADS 503 — Applied Predictive Modeling (University of San Diego, MS-ADS)
**Team:** Group 1
**Language:** R (Quarto / R Markdown)

## Problem Statement

Insurers need to anticipate which policyholders are likely to file a claim so they
can price risk accurately and intervene proactively. Using policy- and
vehicle-level attributes available at underwriting, we frame this as a **binary
classification** problem: *will a policyholder file a claim within the next six
months?* (`is_claim` = 1/0).

## Dataset

[Kaggle — Car Insurance Claim Prediction](https://www.kaggle.com/datasets/ifteshanajnin/carinsuranceclaimprediction-classification)

| | |
|---|---|
| **Labeled rows** (`train.csv`) | 58,592 |
| **Predictors** | 43 (policy tenure, policyholder age, vehicle make/model/segment, engine specs, safety features, NCAP rating, area density, …) |
| **Target** | `is_claim` (1 = claim filed, 0 = no claim) |
| **Class balance** | **~6.4% positive** (severe imbalance) |
| **Missing values** | None — the dataset is complete (verified; no disguised placeholders) |

> ⚠️ **Note on `test.csv`:** the Kaggle `test.csv` has **no `is_claim` label** (hidden
> competition ground truth). It cannot be used to measure model performance. All
> train/validation/test splits in this project are carved from the labeled
> `train.csv`; `test.csv` is reserved only for an optional Kaggle submission.

## Approach

1. **EDA** — target distribution, univariate/bivariate views of key predictors vs. claim status.
2. **Data wrangling & pre-processing** — parse text-encoded specs (`max_torque`,
   `max_power`) into numeric features; encode 17 `Yes`/`No` binaries and nominal
   variables as factors; drop `policy_id`; remove highly correlated predictors
   (`findCorrelation`, |r| > 0.90).
3. **Data splitting** — stratified **60/20/20** train/validation/test (preserves
   the ~6.4% claim rate in each set).
4. **Model strategy** — class imbalance handled via in-fold down-sampling;
   **ROC-AUC** as the primary tuning metric, with sensitivity, specificity,
   balanced accuracy, and F1 reported.
5. **Model building** — logistic regression, penalized logistic (glmnet), PLS-DA,
   MARS (earth), CART, random forest (ranger), and gradient boosting (gbm), each
   tuned via 5-fold cross-validation.
6. **Validation, results & final model selection** — *in progress.*

## Repository Structure

```
.
├── ADS_503_Final_Project.qmd   # Main analysis notebook (EDA → modeling)
├── README.md
├── train.csv                   # Labeled data (used for all modeling)
├── test.csv                    # Kaggle hold-out (unlabeled — submission only)
├── sample_submission.csv       # Kaggle submission template
└── archive/                    # Original downloaded copies of the CSVs
```

## How to Run

Requires **R (≥ 4.5)** and **Quarto**. Install the packages used in the notebook:

```r
install.packages(c(
  "tidyverse", "caret", "glmnet", "earth", "ranger",
  "gbm", "pROC", "corrplot"
))
```

Then render the report:

```bash
quarto render ADS_503_Final_Project.qmd --to html
```

> The model-tuning chunks take a few minutes to run (random forest and GBM are the
> slowest). Add `#| cache: true` to the `train-models` chunk for faster re-renders.

## Status & Division of Work

| Area | Status | Owner |
|---|---|---|
| EDA | Complete | *[teammate]* |
| Data wrangling & pre-processing | Complete | *[teammate]* |
| Data splitting | Complete | *[teammate]* |
| Model strategy & building | Complete | *[teammate]* |
| Validation, results & final model selection | In progress | *[teammate]* |
| Technical report & executive summary | Pending | Team |

## Notes

- **Boosting library:** `xgboost` is currently incompatible with the installed
  `caret` version on our setup (an ALTREP booster-object error), so gradient
  boosting uses **`gbm`** — which is also the textbook (Kuhn & Johnson) choice.
