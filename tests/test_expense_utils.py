import pytest
import pandas as pd
from services.helpers.expense_utils import assign_rounding_diff

MEMBERS = ["Alice", "Bob"]


def make_row(amount, alice_owed, bob_owed):
    return pd.Series({
        "Amount": amount,
        "Alice_share_owed": alice_owed,
        "Bob_share_owed": bob_owed,
    })


class TestAssignRoundingDiff:

    # ------------------------------------------------------------------
    # No adjustment needed
    # ------------------------------------------------------------------

    def test_exact_split_unchanged(self):
        """Shares that already sum to Amount are not modified."""
        row = make_row(1.00, 0.50, 0.50)
        result = assign_rounding_diff(row, MEMBERS)
        assert result["Alice_share_owed"] == 0.50
        assert result["Bob_share_owed"] == 0.50

    def test_zero_shares_unchanged(self):
        """A row with no positive shares is returned as-is."""
        row = make_row(1.00, 0.00, 0.00)
        result = assign_rounding_diff(row, MEMBERS)
        assert result["Alice_share_owed"] == 0.00
        assert result["Bob_share_owed"] == 0.00

    # ------------------------------------------------------------------
    # Uploader absorbs rounding remainder
    # ------------------------------------------------------------------

    def test_uploader_absorbs_remainder_two_people(self):
        """$0.25 / 2 rounds to $0.13 each ($0.26 total); uploader gets $0.12."""
        row = make_row(0.25, 0.13, 0.13)
        result = assign_rounding_diff(row, MEMBERS, current_user_name="Alice")
        assert result["Alice_share_owed"] == 0.12
        assert result["Bob_share_owed"] == 0.13
        assert round(result["Alice_share_owed"] + result["Bob_share_owed"], 2) == 0.25

    def test_uploader_absorbs_shortfall_two_people(self):
        """$1.01 / 2 rounds to $0.50 each ($1.00 total); uploader gets $0.51."""
        row = make_row(1.01, 0.50, 0.50)
        result = assign_rounding_diff(row, MEMBERS, current_user_name="Alice")
        assert result["Alice_share_owed"] == 0.51
        assert result["Bob_share_owed"] == 0.50
        assert round(result["Alice_share_owed"] + result["Bob_share_owed"], 2) == 1.01

    # ------------------------------------------------------------------
    # Large groups — dynamic threshold
    # ------------------------------------------------------------------

    def test_five_person_split(self):
        """$1.00 / 3 in a 5-person group with 3 participants: threshold = 3×0.005."""
        members = ["Alice", "Bob", "Carol", "Dave", "Eve"]
        # $1.00 / 3 = $0.333… → $0.33 each, total $0.99, diff = -$0.01
        row = pd.Series({
            "Amount": 1.00,
            "Alice_share_owed": 0.33,
            "Bob_share_owed": 0.33,
            "Carol_share_owed": 0.33,
            "Dave_share_owed": 0.00,
            "Eve_share_owed": 0.00,
        })
        result = assign_rounding_diff(row, members, current_user_name="Alice")
        assert result["Alice_share_owed"] == 0.34
        total = sum(result[f"{m}_share_owed"] for m in members)
        assert round(total, 2) == 1.00

    def test_old_hardcoded_threshold_would_miss_four_people(self):
        """Regression: the old threshold was abs(diff) < 0.02 (strict), which silently skipped
        the boundary case where 4 participants each round up by half a cent (diff = exactly $0.02).
        $0.98 / 4 = $0.245 → $0.25 each → sum $1.00, diff = +$0.02.
        """
        members = ["A", "B", "C", "D"]
        row = pd.Series({
            "Amount": 0.98,
            "A_share_owed": 0.25,
            "B_share_owed": 0.25,
            "C_share_owed": 0.25,
            "D_share_owed": 0.25,
        })
        result = assign_rounding_diff(row, members, current_user_name="A")
        total = sum(result[f"{m}_share_owed"] for m in members)
        assert round(total, 2) == 0.98

    # ------------------------------------------------------------------
    # Fallback when uploader is not in the expense
    # ------------------------------------------------------------------

    def test_fallback_when_uploader_not_in_expense(self):
        """If uploader has no share, the remainder goes to one of the participants."""
        row = make_row(0.25, 0.00, 0.13)
        # Alice has 0 share (not participating), Bob has 0.13 but total is only 0.13 vs 0.25?
        # More realistic: uploader is Carol, not in this expense
        members = ["Alice", "Bob", "Carol"]
        row = pd.Series({
            "Amount": 0.25,
            "Alice_share_owed": 0.13,
            "Bob_share_owed": 0.13,
            "Carol_share_owed": 0.00,
        })
        result = assign_rounding_diff(row, members, current_user_name="Carol")
        total = sum(result[f"{m}_share_owed"] for m in members)
        assert round(total, 2) == 0.25

    def test_fallback_when_no_uploader_provided(self):
        """current_user_name=None still corrects the total via random fallback."""
        row = make_row(0.25, 0.13, 0.13)
        result = assign_rounding_diff(row, MEMBERS, current_user_name=None)
        total = result["Alice_share_owed"] + result["Bob_share_owed"]
        assert round(total, 2) == 0.25

    # ------------------------------------------------------------------
    # Diff too large — not a rounding artefact, must not be touched
    # ------------------------------------------------------------------

    def test_large_diff_not_modified(self):
        """A difference larger than the rounding threshold is left untouched."""
        row = make_row(10.00, 4.00, 4.00)  # diff = $2.00 — user data error, not rounding
        result = assign_rounding_diff(row, MEMBERS, current_user_name="Alice")
        assert result["Alice_share_owed"] == 4.00
        assert result["Bob_share_owed"] == 4.00
