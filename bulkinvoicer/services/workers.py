"""Worker functions for PDF generation (suitable for ProcessPool)."""

from __future__ import annotations

from typing import Any
import logging
import datetime
from ..config.model import Config
from ..pdf.renderer import PDF

logger = logging.getLogger(__name__)


def generate_client_summary_pdf(config, summary_details) -> tuple[str, bytearray]:
    """Generate summary PDF for all clients."""
    logger.info("Generating summary PDF")

    pdf = PDF(
        config=config,
        cover_page=True,
    )
    pdf.set_title("Overall Summary")

    pdf.add_combined_summary(summary_details, toc_level=0)

    return "summary", pdf.output()


def generate_client_pdf(
    config: Config,
    client_id: str,
    client_invoices: list[dict[str, Any]],
    client_receipts: list[dict[str, Any]],
    client_transactions: list[dict[str, Any]] | None,
    reporting_period_text: str | None,
    include_summary: bool,
    client_summary: dict[str, Any],
    monthly_summary: list[dict[str, Any]] | None,
) -> tuple[str, bytearray]:
    """Generate PDF for a single client."""
    logger.debug(f"Generating PDF for client: {client_id}")

    pdf = PDF(
        config=config,
        cover_page=include_summary,
    )
    pdf.set_title(client_id)

    # Add client summary if available
    if include_summary:
        key_figures = [
            (
                "Opening Balance",
                client_summary["opening_balance"],
                f"({'Due' if client_summary['opening_balance'] > 0 else 'Advance'})"
                if client_summary["opening_balance"] != 0
                else "",
            ),
            (
                "Total Billed",
                client_summary["invoice_total"],
                f"({client_summary['invoice_count']} invoices)",
            ),
            (
                "Total Paid",
                client_summary["receipt_total"],
                f"({client_summary['receipt_count']} receipts)",
            ),
            (
                "Closing Balance",
                client_summary["closing_balance"],
                f"({'Due' if client_summary['closing_balance'] > 0 else 'Advance'})"
                if client_summary["closing_balance"] != 0
                else "",
                "#ffcccc" if client_summary["closing_balance"] > 0 else None,
            ),
        ]

        if client_transactions is None or monthly_summary is None:
            raise ValueError(
                f"Transactions or monthly summary data for client {client_id} is missing."
            )

        pdf.add_client_summary(
            client=client_id,
            client_display_name=client_summary["client_display_name"],
            client_address=client_summary["client_address"],
            client_phone=client_summary["client_phone"],
            client_email=client_summary["client_email"],
            generated=f"Generated: {datetime.datetime.now().strftime(config.invoice.date_format)}",
            period=reporting_period_text,
            key_figures=key_figures,
            monthly_summary=monthly_summary,
            transactions=client_transactions,
            outstanding=client_summary["closing_balance"],
            toc_level=1,
        )

        logger.debug(f"Client summary for {client_id} added to PDF.")

    for i, invoice_data in enumerate(client_invoices):
        pdf.generate_invoice(
            invoice_data,
            start_section=i == 0,
            create_toc_entry=True,
        )

    logger.debug(f"Invoices for client {client_id} generated successfully.")

    for i, receipt_data in enumerate(client_receipts):
        pdf.generate_receipt(
            receipt_data,
            start_section=i == 0,
            create_toc_entry=True,
        )

    logger.debug(f"Receipts for client {client_id} generated successfully.")

    return client_id, pdf.output()


def generate_invoice_pdf(
    config: Config, invoice_data: dict[str, Any]
) -> tuple[str, bytearray]:
    """Generate a single invoice PDF."""
    pdf = PDF(config=config)
    pdf.set_title(f"Invoice {invoice_data['number']}")
    pdf.generate_invoice(
        invoice_data,
        start_section=False,
        create_toc_entry=False,
    )
    return invoice_data["number"], pdf.output()


def generate_receipt_pdf(
    config: Config, receipt_data: dict[str, Any]
) -> tuple[str, bytearray]:
    """Generate a single receipt PDF."""
    pdf = PDF(config=config)
    pdf.set_title(f"Receipt {receipt_data['number']}")
    pdf.generate_receipt(
        receipt_data,
        start_section=False,
        create_toc_entry=False,
    )
    return receipt_data["number"], pdf.output()
