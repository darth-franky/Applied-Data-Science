from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

from data_io import load_prepared_data


DATA_PATH = Path(
    "data/processed/get_it_done_requests_closed_2025_prepared.csv.gz"
)

OUTPUT_DIR = Path("outputs/evaluation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # Load prepared data
    df = load_prepared_data(DATA_PATH)

    print(f"Loaded {len(df):,} prepared rows.")

    # Primary evaluation:
    # exclude parent-child requests
    df = df.loc[~df["has_parent_request"]].copy()

    # Remove ambiguous repeated descriptions
    df = df.loc[~df["is_ambiguous_description"]].copy()

    # Keep categories with at least 200 observations
    category_counts = df["service_name"].value_counts()
    valid_categories = category_counts[category_counts >= 200].index

    df = df[df["service_name"].isin(valid_categories)].copy()

    print(f"Rows after filtering: {len(df):,}")
    print(f"Categories included: {df['service_name'].nunique()}")

    X = df["public_description_clean"]
    y = df["service_name"]
    groups = df["description_group_id"]

    # Group-aware split prevents identical descriptions
    # from appearing in both train and test sets
    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.20,
        random_state=42,
    )

    train_idx, test_idx = next(
        splitter.split(X, y, groups=groups)
    )

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    test_df = df.iloc[test_idx][
        [
            "service_request_id",
            "public_description_clean",
            "service_name",
            "description_group_id",
        ]
    ].copy()

    test_df.to_csv(
        OUTPUT_DIR / "evaluation_sample.csv",
        index=False,
    )

    print(f"Training rows: {len(X_train):,}")
    print(f"Test rows: {len(X_test):,}")

    # --------------------------------------------------
    # Majority-class baseline
    # --------------------------------------------------

    majority_model = DummyClassifier(strategy="most_frequent")
    majority_model.fit(X_train.to_frame(), y_train)

    majority_pred = majority_model.predict(X_test.to_frame())

    majority_accuracy = accuracy_score(y_test, majority_pred)
    majority_macro_f1 = f1_score(
        y_test,
        majority_pred,
        average="macro",
        zero_division=0,
    )

    # --------------------------------------------------
    # TF-IDF + Logistic Regression
    # --------------------------------------------------

    tfidf_model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=50_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )

    print("Training TF-IDF + Logistic Regression...")
    tfidf_model.fit(X_train, y_train)

    tfidf_pred = tfidf_model.predict(X_test)

    tfidf_accuracy = accuracy_score(y_test, tfidf_pred)
    tfidf_macro_f1 = f1_score(
        y_test,
        tfidf_pred,
        average="macro",
        zero_division=0,
    )
    # --------------------------------------------------
    # Confusion matrix
    # --------------------------------------------------

    labels = sorted(y_test.unique())

    cm = confusion_matrix(
        y_test,
        tfidf_pred,
        labels=labels,
    )

    fig, ax = plt.subplots(figsize=(18, 18))

    disp = ConfusionMatrixDisplay(
        confusion_matrix=cm,
        display_labels=labels,
    )

    disp.plot(
        ax=ax,
        xticks_rotation=90,
        cmap="Blues",
        colorbar=False,
        values_format="d",
    )

    plt.title("TF-IDF + Logistic Regression Confusion Matrix")
    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / "tfidf_confusion_matrix.png",
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()
    # --------------------------------------------------
    # Overall metrics
    # --------------------------------------------------

    metrics = pd.DataFrame(
        [
            {
                "model": "Majority Class",
                "accuracy": majority_accuracy,
                "macro_f1": majority_macro_f1,
            },
            {
                "model": "TF-IDF + Logistic Regression",
                "accuracy": tfidf_accuracy,
                "macro_f1": tfidf_macro_f1,
            },
        ]
    )

    metrics.to_csv(
        OUTPUT_DIR / "baseline_metrics.csv",
        index=False,
    )

    # --------------------------------------------------
    # Per-category metrics
    # --------------------------------------------------

    report = classification_report(
        y_test,
        tfidf_pred,
        output_dict=True,
        zero_division=0,
    )

    report_df = pd.DataFrame(report).transpose()

    report_df.to_csv(
        OUTPUT_DIR / "tfidf_classification_report.csv"
    )

    # Save predictions
    predictions = test_df.copy()
    predictions["majority_prediction"] = majority_pred
    predictions["tfidf_prediction"] = tfidf_pred

    predictions.to_csv(
        OUTPUT_DIR / "baseline_predictions.csv",
        index=False,
    )

    # --------------------------------------------------
    # Print summary
    # --------------------------------------------------

    print("\nBaseline Results")
    print("-------------------------------")
    print(
        f"Majority-class accuracy: {majority_accuracy:.4f}"
    )
    print(
        f"Majority-class macro F1: {majority_macro_f1:.4f}"
    )
    print()
    print(
        f"TF-IDF Logistic Regression accuracy: "
        f"{tfidf_accuracy:.4f}"
    )
    print(
        f"TF-IDF Logistic Regression macro F1: "
        f"{tfidf_macro_f1:.4f}"
    )

    print("\nSaved results to:")
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()