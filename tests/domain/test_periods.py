"""Tests for bulkinvoicer.domain.periods."""

import datetime as dt
import logging
import pytest
import polars as pl

from bulkinvoicer.domain.periods import (
    get_reporting_period_text,
    slice_period_frames,
)


class TestGetReportingPeriodText:
    """Test suite for the `get_reporting_period_text` function."""

    def test_both_dates_valid(self):
        """Test with both start and end dates provided."""
        start = dt.date(2024, 1, 1)
        end = dt.date(2024, 1, 31)
        fmt = "%Y-%m-%d"
        out = get_reporting_period_text(fmt, start, end)
        assert out == "Period: 2024-01-01 - 2024-01-31"

    def test_only_start_date(self):
        """Test with only start date provided."""
        start = dt.date(2024, 2, 15)
        out = get_reporting_period_text("%d %b %Y", start, None)
        assert out == "Period: Starting 15 Feb 2024"

    def test_only_end_date(self):
        """Test with only end date provided."""
        end = dt.date(2024, 3, 10)
        out = get_reporting_period_text("%b %d, %Y", None, end)
        assert out == "Period: Ending Mar 10, 2024"

    def test_no_dates_returns_none(self):
        """Test with neither date provided returns None."""
        assert get_reporting_period_text("%Y-%m-%d", None, None) is None

    def test_start_after_end_raises_and_logs(self, caplog):
        """Test that start date after end date raises ValueError and logs error."""
        start = dt.date(2024, 5, 2)
        end = dt.date(2024, 5, 1)
        with caplog.at_level(logging.ERROR, logger="bulkinvoicer.domain.periods"):
            with pytest.raises(ValueError) as excinfo:
                get_reporting_period_text("%Y-%m-%d", start, end)
        assert "cannot be after" in str(excinfo.value)
        assert any("is after end date" in rec.getMessage() for rec in caplog.records)


class TestSlicePeriodFrames:
    """Test suite for the `slice_period_frames` function."""

    def _make_sample_frames(self):
        """Create sample invoices and receipts frames for testing."""
        invoices = pl.DataFrame(
            {
                "sort_date": [
                    dt.date(2024, 1, 1),  # before start
                    dt.date(2024, 1, 10),  # at start
                    dt.date(2024, 1, 20),  # at end
                ],
                "date": [
                    dt.date(2024, 1, 1),
                    dt.date(2024, 1, 10),
                    dt.date(2024, 1, 20),
                ],
                "client": ["C1", "C1", "C1"],
                # numbers intentionally unsorted to test sorting by "number" in report frames
                "number": ["INV-B", "INV-A", "INV-C"],
                "total": [100, 200, 300],
            }
        )
        receipts = pl.DataFrame(
            {
                "sort_date": [
                    dt.date(2024, 1, 1),  # before start
                    dt.date(2024, 1, 10),  # at start
                    dt.date(2024, 1, 25),  # after end
                ],
                "date": [
                    dt.date(2024, 1, 1),
                    dt.date(2024, 1, 10),
                    dt.date(2024, 1, 25),
                ],
                "client": ["C1", "C1", "C1"],
                "number": ["REC-B", "REC-A", "REC-C"],
                "amount": [50, 75, 125],
            }
        )
        return invoices, receipts

    def test_both_bounds_filters_and_sorts(self):
        """Test with both start and end dates provided."""
        invoices, receipts = self._make_sample_frames()
        start = dt.date(2024, 1, 10)
        end = dt.date(2024, 1, 20)

        frames = slice_period_frames(invoices, receipts, start, end)

        inv_report = frames["invoices_report"]
        rec_report = frames["receipts_report"]
        inv_open = frames["invoices_open"]
        rec_open = frames["receipts_open"]
        inv_close = frames["invoices_close"]
        rec_close = frames["receipts_close"]

        # Report frames: only within [start, end], inclusive, and sorted by number
        assert inv_report.select("sort_date").to_series().to_list() == [
            dt.date(2024, 1, 10),
            dt.date(2024, 1, 20),
        ]
        # Sorted alphabetically by "number": INV-A then INV-C
        assert inv_report.select("number").to_series().to_list() == ["INV-A", "INV-C"]

        # Receipts report: only at start (10th); 25th excluded by end bound
        assert rec_report.select("sort_date").to_series().to_list() == [
            dt.date(2024, 1, 10)
        ]
        assert rec_report.select("number").to_series().to_list() == ["REC-A"]

        # Open frames: strictly before start
        assert inv_open.select("number").to_series().to_list() == ["INV-B"]
        assert rec_open.select("number").to_series().to_list() == ["REC-B"]

        # Close frames: up to and including end
        assert set(inv_close.select("number").to_series().to_list()) == {
            "INV-B",
            "INV-A",
            "INV-C",
        }
        assert set(rec_close.select("number").to_series().to_list()) == {
            "REC-B",
            "REC-A",
        }

    def test_start_only_open_and_report(self):
        """Test with only start date provided."""
        invoices, receipts = self._make_sample_frames()
        start = dt.date(2024, 1, 10)

        frames = slice_period_frames(invoices, receipts, start, None)

        inv_report = frames["invoices_report"]
        rec_report = frames["receipts_report"]
        inv_open = frames["invoices_open"]
        rec_open = frames["receipts_open"]
        inv_close = frames["invoices_close"]
        rec_close = frames["receipts_close"]

        # Report frames: >= start, sorted by number
        assert inv_report.select("sort_date").to_series().to_list() == [
            dt.date(2024, 1, 10),
            dt.date(2024, 1, 20),
        ]
        assert inv_report.select("number").to_series().to_list() == ["INV-A", "INV-C"]

        assert rec_report.select("sort_date").to_series().to_list() == [
            dt.date(2024, 1, 10),
            dt.date(2024, 1, 25),
        ]
        assert rec_report.select("number").to_series().to_list() == ["REC-A", "REC-C"]

        # Open frames: < start only
        assert inv_open.select("number").to_series().to_list() == ["INV-B"]
        assert rec_open.select("number").to_series().to_list() == ["REC-B"]

        # Close frames: unchanged (no end bound applied)
        assert set(inv_close.select("number").to_series().to_list()) == {
            "INV-B",
            "INV-A",
            "INV-C",
        }
        assert set(rec_close.select("number").to_series().to_list()) == {
            "REC-B",
            "REC-A",
            "REC-C",
        }

    def test_end_only_open_empty_close_filtered(self):
        """Test with only end date provided."""
        invoices, receipts = self._make_sample_frames()
        end = dt.date(2024, 1, 10)

        frames = slice_period_frames(invoices, receipts, None, end)

        inv_report = frames["invoices_report"]
        rec_report = frames["receipts_report"]
        inv_open = frames["invoices_open"]
        rec_open = frames["receipts_open"]
        inv_close = frames["invoices_close"]
        rec_close = frames["receipts_close"]

        print(inv_report)

        # Report frames: <= end, sorted by number
        assert inv_report.select("sort_date").to_series().to_list() == [
            dt.date(2024, 1, 10),
            dt.date(2024, 1, 1),
        ]

        assert inv_report.select("number").to_series().to_list() == [
            "INV-A",
            "INV-B",
        ]
        # Because sorting by number is applied, expected order is alphabetical:
        assert inv_report.select("number").to_series().to_list() == ["INV-A", "INV-B"]

        assert rec_report.select("sort_date").to_series().to_list() == [
            dt.date(2024, 1, 10),
            dt.date(2024, 1, 1),
        ]
        assert rec_report.select("number").to_series().to_list() == ["REC-A", "REC-B"]

        # Open frames: empty when no start bound
        assert inv_open.height == 0
        assert rec_open.height == 0

        # Close frames: <= end only
        assert set(inv_close.select("number").to_series().to_list()) == {
            "INV-B",
            "INV-A",
        }
        assert set(rec_close.select("number").to_series().to_list()) == {
            "REC-B",
            "REC-A",
        }

    def test_no_bounds(self):
        """Test with neither start nor end date provided."""
        invoices, receipts = self._make_sample_frames()

        frames = slice_period_frames(invoices, receipts, None, None)

        inv_report = frames["invoices_report"]
        rec_report = frames["receipts_report"]
        inv_open = frames["invoices_open"]
        rec_open = frames["receipts_open"]
        inv_close = frames["invoices_close"]
        rec_close = frames["receipts_close"]

        # Report frames should be all rows but sorted by number
        assert inv_report.height == invoices.height
        assert inv_report.select("number").to_series().to_list() == [
            "INV-A",
            "INV-B",
            "INV-C",
        ]

        assert rec_report.height == receipts.height
        assert rec_report.select("number").to_series().to_list() == [
            "REC-A",
            "REC-B",
            "REC-C",
        ]

        # Open frames empty
        assert inv_open.height == 0
        assert rec_open.height == 0

        # Close frames unchanged
        assert set(inv_close.select("number").to_series().to_list()) == set(
            invoices.select("number").to_series().to_list()
        )
        assert set(rec_close.select("number").to_series().to_list()) == set(
            receipts.select("number").to_series().to_list()
        )

    def test_inclusive_boundaries_in_report_frames(self):
        """Test that boundary dates are included in report frames."""
        invoices = pl.DataFrame(
            {
                "sort_date": [
                    dt.date(2024, 2, 1),
                    dt.date(2024, 2, 15),
                    dt.date(2024, 2, 28),
                ],
                "date": [
                    dt.date(2024, 2, 1),
                    dt.date(2024, 2, 15),
                    dt.date(2024, 2, 28),
                ],
                "client": ["C1", "C1", "C1"],
                "number": ["INV-1", "INV-2", "INV-3"],
                "total": [10, 20, 30],
            }
        )
        receipts = pl.DataFrame(
            {
                "sort_date": [dt.date(2024, 2, 1), dt.date(2024, 2, 28)],
                "date": [dt.date(2024, 2, 1), dt.date(2024, 2, 28)],
                "client": ["C1", "C1"],
                "number": ["REC-1", "REC-2"],
                "amount": [1, 2],
            }
        )
        start = dt.date(2024, 2, 1)
        end = dt.date(2024, 2, 28)

        frames = slice_period_frames(invoices, receipts, start, end)

        # All boundary elements should be included (inclusive)
        assert frames["invoices_report"].select("number").to_series().to_list() == [
            "INV-1",
            "INV-2",
            "INV-3",
        ]
        assert frames["receipts_report"].select("number").to_series().to_list() == [
            "REC-1",
            "REC-2",
        ]
