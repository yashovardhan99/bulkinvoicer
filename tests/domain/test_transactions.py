"""Tests for transactions domain logic."""

import datetime as dt
import polars as pl
from bulkinvoicer.domain.transactions import build_client_transactions_df


class TestTransactions:
    """Test suite for verifying the behavior of the `build_client_transactions_df` function.

    This class contains tests to ensure correct partitioning, sorting, filtering, and mapping of client transactions
    from invoices and receipts data. The tests cover the following scenarios:

    - Partitioning balances for multiple clients and correct running balance calculation.
    - Ensuring output DataFrame is sorted by `sort_date`.
    - Verifying date filter boundaries are inclusive.
    - Handling cases with only invoices or only receipts.
    - Correct mapping of transaction references and types.

    Each test constructs sample invoice and receipt data using Polars DataFrames and asserts the correctness of the
    resulting transactions DataFrame produced by `build_client_transactions_df`.
    """

    def test_multiple_clients_balance_partitioning(self):
        """Test that balances are correctly partitioned by client."""
        invoices = pl.DataFrame(
            {
                "sort_date": [
                    dt.date(2024, 1, 1),
                    dt.date(2024, 1, 2),
                    dt.date(2024, 1, 3),
                ],
                "date": [
                    dt.date(2024, 1, 1),
                    dt.date(2024, 1, 2),
                    dt.date(2024, 1, 3),
                ],
                "client": ["C1", "C2", "C1"],
                "number": ["INV-1", "INV-A", "INV-2"],
                "total": [100, 30, 50],
            }
        )
        receipts = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 1, 2), dt.date(2024, 1, 4)],
                "date": [dt.date(2024, 1, 2), dt.date(2024, 1, 4)],
                "client": ["C1", "C2"],
                "number": ["REC-1", "REC-2"],
                "amount": [40, 10],
            }
        )
        df = build_client_transactions_df(
            dt.date(2024, 1, 1), dt.date(2024, 1, 31), invoices, receipts
        )
        assert df.height == 5

        df_c1 = df.filter(pl.col("client") == "C1")
        assert df_c1.select("amount").to_series().to_list() == [100, -40, 50]
        assert df_c1.select("balance").to_series().to_list() == [100, 60, 110]

        df_c2 = df.filter(pl.col("client") == "C2")
        assert df_c2.select("amount").to_series().to_list() == [30, -10]
        assert df_c2.select("balance").to_series().to_list() == [30, 20]

    def test_output_is_sorted_by_sort_date(self):
        """Test that the output DataFrame is sorted by `sort_date`."""
        invoices = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 1, 5), dt.date(2024, 1, 1)],
                "date": [dt.date(2024, 1, 5), dt.date(2024, 1, 1)],
                "client": ["C1", "C1"],
                "number": ["INV-2", "INV-1"],
                "total": [50, 100],
            }
        )
        receipts = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 1, 3)],
                "date": [dt.date(2024, 1, 3)],
                "client": ["C1"],
                "number": ["REC-1"],
                "amount": [60],
            }
        )
        df = build_client_transactions_df(
            dt.date(2024, 1, 1), dt.date(2024, 1, 31), invoices, receipts
        )
        # Ensure sort_date is non-decreasing
        sort_dates = df.select("sort_date").to_series().to_list()
        assert sort_dates == sorted(sort_dates)

    def test_date_filter_boundaries_inclusive(self):
        """Test that the date filter boundaries are inclusive."""
        invoices = pl.DataFrame(
            {
                "sort_date": [
                    dt.date(2024, 1, 1),
                    dt.date(2024, 1, 2),
                    dt.date(2024, 1, 3),
                ],
                "date": [
                    dt.date(2024, 1, 1),
                    dt.date(2024, 1, 2),
                    dt.date(2024, 1, 3),
                ],
                "client": ["C1", "C1", "C1"],
                "number": ["INV-1", "INV-2", "INV-3"],
                "total": [10, 20, 30],
            }
        )
        receipts = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 1, 2)],
                "date": [dt.date(2024, 1, 2)],
                "client": ["C1"],
                "number": ["REC-1"],
                "amount": [5],
            }
        )
        df = build_client_transactions_df(
            dt.date(2024, 1, 2), dt.date(2024, 1, 2), invoices, receipts
        )
        # Only events on Jan 2 should be present
        assert df.height == 2
        assert set(df.select("reference").to_series().to_list()) == {
            "INV-2",
            "REC-1",
        }

        df2 = build_client_transactions_df(
            dt.date(2024, 1, 2), dt.date(2024, 1, 3), invoices, receipts
        )
        assert df2.select("sort_date").to_series().to_list() == [
            dt.date(2024, 1, 2),
            dt.date(2024, 1, 2),
            dt.date(2024, 1, 3),
        ]

    def test_only_invoices(self):
        """Test handling of cases with only invoices and no receipts."""
        invoices = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
                "date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
                "client": ["C1", "C1"],
                "number": ["INV-1", "INV-2"],
                "total": [100, 50],
            }
        )
        receipts = invoices.head(0).with_columns(
            pl.Series("amount", [], dtype=pl.Int64)
        )
        df = build_client_transactions_df(
            dt.date(2024, 1, 1), dt.date(2024, 1, 31), invoices, receipts
        )
        assert df.height == 2
        assert df.select("type").to_series().to_list() == ["Invoice", "Invoice"]
        assert df.select("amount").to_series().to_list() == [100, 50]
        assert df.select("balance").to_series().to_list() == [100, 150]

    def test_only_receipts(self):
        """Test handling of cases with only receipts and no invoices."""
        invoices = pl.DataFrame(
            {
                "sort_date": [],
                "date": [],
                "client": [],
                "number": [],
                "total": [],
            }
        ).cast(
            {
                "sort_date": pl.Date,
                "date": pl.Date,
                "client": pl.Utf8,
                "number": pl.Utf8,
                "total": pl.Int64,
            }
        )
        receipts = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
                "date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
                "client": ["C1", "C1"],
                "number": ["REC-1", "REC-2"],
                "amount": [25, 10],
            }
        )
        df = build_client_transactions_df(
            dt.date(2024, 1, 1), dt.date(2024, 1, 31), invoices, receipts
        )
        assert df.height == 2
        assert df.select("type").to_series().to_list() == ["Receipt", "Receipt"]
        assert df.select("amount").to_series().to_list() == [-25, -10]
        assert df.select("balance").to_series().to_list() == [-25, -35]

    def test_reference_and_type_mapping(self):
        """Test that transaction references and types are correctly mapped."""
        invoices = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 2, 1)],
                "date": [dt.date(2024, 2, 1)],
                "client": ["C1"],
                "number": ["INV-100"],
                "total": [200],
            }
        )
        receipts = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 2, 2)],
                "date": [dt.date(2024, 2, 2)],
                "client": ["C1"],
                "number": ["REC-200"],
                "amount": [150],
            }
        )
        df = build_client_transactions_df(
            dt.date(2024, 2, 1), dt.date(2024, 2, 28), invoices, receipts
        )
        assert df.select("type").to_series().to_list() == ["Invoice", "Receipt"]
        assert df.select("reference").to_series().to_list() == [
            "INV-100",
            "REC-200",
        ]
        assert df.select("amount").to_series().to_list() == [200, -150]
        assert df.select("balance").to_series().to_list() == [200, 50]
