"""Unit tests for the highest-risk text preparation behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prepare_data import (  # noqa: E402
    EMAIL_PATTERN,
    LICENSE_PLATE_PATTERN,
    PHONE_PATTERN,
    URL_PATTERN,
    has_semantic_text,
    mask_known_street_addresses,
    sanitize_text,
)


class PrepareDataTests(unittest.TestCase):
    def test_second_pass_masks_identifiers_exposed_by_phone_mask(self) -> None:
        source = pd.Series(
            [
                "6195551212www.example.com/report",
                "6195551212name@example.com",
            ],
            dtype="string",
        )

        cleaned = sanitize_text(source)

        self.assertFalse(cleaned.str.contains(EMAIL_PATTERN, regex=True).any())
        self.assertFalse(cleaned.str.contains(URL_PATTERN, regex=True).any())
        self.assertFalse(cleaned.str.contains(PHONE_PATTERN, regex=True).any())
        self.assertTrue(cleaned.str.contains(r"\[(?:EMAIL|URL)\]", regex=True).all())

    def test_known_local_address_is_masked_case_insensitively(self) -> None:
        descriptions = pd.Series(
            ["Issue reported near 2632 Broadway", "No address supplied"],
            dtype="string",
        )
        addresses = pd.Series(
            ["2632 BROADWAY", "4020 VIA DE LA BANDOLA"], dtype="string"
        )

        masked, flags = mask_known_street_addresses(descriptions, addresses)

        self.assertEqual(masked.iloc[0], "Issue reported near [ADDRESS]")
        self.assertEqual(flags.tolist(), [True, False])

    def test_contextual_license_plate_is_masked(self) -> None:
        source = pd.Series(["Vehicle plate 8ABC123 is blocking access"])

        cleaned = sanitize_text(source)

        self.assertIn("[LICENSE_PLATE]", cleaned.iloc[0])
        self.assertFalse(
            cleaned.str.contains(LICENSE_PLATE_PATTERN, regex=True).any()
        )

    def test_semantic_text_excludes_placeholders_and_punctuation(self) -> None:
        source = pd.Series(
            ["[ADDRESS]", "...", "[PHONE] pothole", "graffiti"],
            dtype="string",
        )

        self.assertEqual(has_semantic_text(source).tolist(), [False, False, True, True])

    def test_redacted_variants_create_the_same_model_input(self) -> None:
        source = pd.Series(
            ["Contact first@example.com", "Contact second@example.com"],
            dtype="string",
        )

        cleaned = sanitize_text(source).str.casefold()

        self.assertEqual(cleaned.nunique(), 1)


if __name__ == "__main__":
    unittest.main()
