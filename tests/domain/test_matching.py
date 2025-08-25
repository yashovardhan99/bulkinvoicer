"""Tests for matching payments to invoices by client."""

import datetime as dt
import logging
from typing import Any
import polars as pl
from bulkinvoicer.domain.matching import match_payments_by_client


def _make_empty_invoices() -> pl.DataFrame:
    """Create an empty invoices DataFrame with the expected schema."""
    return pl.DataFrame(
        schema={
            "sort_date": pl.Date,
            "date": pl.Date,
            "client": pl.Utf8,
            "number": pl.Utf8,
            "total": pl.Int64,
        }
    )


def _make_empty_receipts() -> pl.DataFrame:
    """Create an empty receipts DataFrame with the expected schema."""
    return pl.DataFrame(
        schema={
            "sort_date": pl.Date,
            "date": pl.Date,
            "client": pl.Utf8,
            "number": pl.Utf8,
            "amount": pl.Int64,
        }
    )


def _make_sample_data() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Create sample invoices and receipts DataFrames for testing."""
    invoices = pl.DataFrame(
        {
            "sort_date": [
                dt.date(2024, 1, 1),  # C1 inv1
                dt.date(2024, 1, 10),  # C1 inv2 (last for C1)
                dt.date(2024, 1, 5),  # C2 inv1 (last for C2)
                dt.date(2024, 1, 7),  # C3 inv1 (no receipts)
            ],
            "date": [
                dt.date(2024, 1, 1),
                dt.date(2024, 1, 10),
                dt.date(2024, 1, 5),
                dt.date(2024, 1, 7),
            ],
            "client": ["C1", "C1", "C2", "C3"],
            "number": ["INV-C1-1", "INV-C1-2", "INV-C2-1", "INV-C3-1"],
            "total": [100, 50, 200, 300],
        }
    )
    receipts = pl.DataFrame(
        {
            "sort_date": [
                dt.date(2024, 1, 2),  # C1 receipt
                dt.date(2024, 1, 6),  # C2 receipt 1
                dt.date(2024, 1, 7),  # C2 receipt 2
                dt.date(2024, 1, 3),  # C4 receipt (no invoices)
            ],
            "date": [
                dt.date(2024, 1, 2),
                dt.date(2024, 1, 6),
                dt.date(2024, 1, 7),
                dt.date(2024, 1, 3),
            ],
            "client": ["C1", "C2", "C2", "C4"],
            "number": ["REC-C1-1", "REC-C2-1", "REC-C2-2", "REC-C4-1"],
            "amount": [80, 50, 120, 25],
        }
    )
    return invoices, receipts


class TestMatchPaymentsByClient:
    """Tests for match_payments_by_client function."""

    def test_both_empty_returns_same_and_logs_warning(self, caplog):
        """Test that both empty DataFrames return same and log a warning."""
        df_invoices = _make_empty_invoices()
        df_receipts = _make_empty_receipts()

        with caplog.at_level(logging.WARNING, logger="bulkinvoicer.domain.matching"):
            out_inv, out_rec = match_payments_by_client(df_invoices, df_receipts)

        assert out_inv is df_invoices
        assert out_rec is df_receipts
        assert any(
            "No invoices or receipts to match." in r.getMessage()
            for r in caplog.records
        )

    def test_no_receipts_adds_balance_and_receipts_unchanged(self):
        """Test that no receipts returns invoices with balance=total and receipts unchanged."""
        df_invoices = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
                "date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
                "client": ["C1", "C1"],
                "number": ["INV-1", "INV-2"],
                "total": [150, 250],
            }
        )
        df_receipts = _make_empty_receipts()

        out_inv, out_rec = match_payments_by_client(df_invoices, df_receipts)

        # receipts returned unchanged (identity)
        assert out_rec is df_receipts

        # balance equals total for each invoice (cast to Int64 for easy compare)
        totals = out_inv.select("total").to_series().to_list()
        balances = (
            out_inv.select(pl.col("balance").cast(pl.Int64)).to_series().to_list()
        )
        assert balances == totals

    def test_matching_with_stub_per_client_joins_and_logs(self, monkeypatch, caplog):
        """Test matching with a stubbed match_payments function per client."""

        # Stub match_payments used inside module under test
        def stub_match_payments(inv: list[dict[str, Any]], rec: list[dict[str, Any]]):
            matched = [
                {
                    "receipt": r["number"],
                    "invoices": ([inv[0]["number"]] if inv else []),
                }
                for r in rec
            ]
            total_receipts = sum(r["amount"] for r in rec) if rec else 0
            unpaid = (
                [
                    {
                        "number": inv[-1]["number"],
                        "balance": inv[-1]["total"] - total_receipts,
                    }
                ]
                if inv
                else []
            )
            return matched, unpaid

        monkeypatch.setattr(
            "bulkinvoicer.domain.matching.match_payments", stub_match_payments
        )

        invoices, receipts = _make_sample_data()

        with caplog.at_level(logging.INFO, logger="bulkinvoicer.domain.matching"):
            out_inv, out_rec = match_payments_by_client(invoices, receipts)

        # Assert info logs present
        msgs = [r.getMessage() for r in caplog.records]
        assert any("Matching payments to invoices." in m for m in msgs)
        assert any("Payments matched to invoices." in m for m in msgs)

        # Receipts joined with invoices list per receipt
        rec_map = {
            r["number"]: r.get("invoices")
            for r in out_rec.select("number", "invoices").to_dicts()
        }
        assert rec_map["REC-C1-1"] == ["INV-C1-1"]  # first invoice for C1
        assert rec_map["REC-C2-1"] == ["INV-C2-1"]  # first (and only) invoice for C2
        assert rec_map["REC-C2-2"] == ["INV-C2-1"]
        assert rec_map["REC-C4-1"] == []  # no invoices for C4 -> empty list from stub

        # Invoices joined with unpaid balances for last invoice per client (others None)
        inv_bal_df = out_inv.select(pl.col("number"), pl.col("balance").cast(pl.Int64))
        inv_bal = {r["number"]: r["balance"] for r in inv_bal_df.to_dicts()}
        # For C1: last invoice is INV-C1-2 total 50, receipts sum=80 => balance = -30
        assert inv_bal["INV-C1-2"] == -30
        # For C2: last invoice is INV-C2-1 total 200, receipts sum=170 => balance = 30
        assert inv_bal["INV-C2-1"] == 30
        # For invoices not in unpaid set -> None
        assert inv_bal["INV-C1-1"] is None
        assert inv_bal["INV-C3-1"] is None

    def test_no_matches_path_empty_matched_and_unpaid_creates_null_columns(
        self, monkeypatch, caplog
    ):
        """Test path where no matches and no unpaid invoices returns null columns."""

        # Stub returns no matches and no unpaid invoices for all clients
        def stub_noop_match_payments(inv, rec):
            return [], []

        monkeypatch.setattr(
            "bulkinvoicer.domain.matching.match_payments", stub_noop_match_payments
        )

        invoices = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
                "date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
                "client": ["C1", "C2"],
                "number": ["INV-1", "INV-2"],
                "total": [100, 200],
            }
        )
        receipts = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 1, 3), dt.date(2024, 1, 4)],
                "date": [dt.date(2024, 1, 3), dt.date(2024, 1, 4)],
                "client": ["C1", "C2"],
                "number": ["REC-1", "REC-2"],
                "amount": [60, 40],
            }
        )

        with caplog.at_level(logging.INFO, logger="bulkinvoicer.domain.matching"):
            out_inv, out_rec = match_payments_by_client(invoices, receipts)

        # Receipts have 'invoices' column with nulls (no matches)
        invoices_col = out_rec.select("invoices").to_series().to_list()
        assert invoices_col == [None, None]

        # Invoices have 'balance' column with nulls (no unpaid data returned)
        balances = out_inv.select("balance").to_series().to_list()
        assert balances == [None, None]

        # Info logs present
        msgs = [r.getMessage() for r in caplog.records]
        assert any("Matching payments to invoices." in m for m in msgs)
        assert any("Payments matched to invoices." in m for m in msgs)
