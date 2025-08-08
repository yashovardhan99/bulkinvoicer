"""Common utility functions for the Bulkinvoicer application."""

from decimal import Decimal
import logging
from collections.abc import Mapping, Sequence
from typing import Any

import qrcode
from fpdf import FPDF, FontFace

logger = logging.getLogger(__name__)


class PDF(FPDF):
    """Custom PDF class to handle specific PDF generation tasks."""

    def __init__(
        self,
        orientation="portrait",
        unit="mm",
        format="A4",
        font_cache_dir="DEPRECATED",
        config: Mapping[str, Any] = {},
        cover_page: bool = False,
    ):
        """Initialize the PDF with optional configuration."""
        super().__init__(orientation, unit, format, font_cache_dir)
        self.config = config
        self.set_author(config["seller"]["name"])
        self.set_creator("Bulkinvoicer")
        self.set_lang("en-IN")
        self.cover_page = cover_page

    def header(self) -> None:
        """Define the header for the PDF."""
        if self.cover_page and self.page_no() == 1:
            logger.info("Skipping header for cover page.")
            return

        self.set_font("courier", size=16, style="B")
        self.cell(
            0,
            text=self.config["seller"]["name"].upper(),
            new_x="LMARGIN",
            new_y="NEXT",
            align="C",
            markdown=True,
        )
        if "tagline" in self.config["seller"]:
            self.set_font("helvetica", size=8, style="I")
            self.cell(
                0,
                text=self.config["seller"]["tagline"],
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
                markdown=True,
            )

        self.ln(20)

    def footer(self) -> None:
        """Define the footer for the PDF."""
        if self.cover_page and self.page_no() == 1:
            logger.info("Skipping footer for cover page.")
            return

        if "footer" in self.config and "text" in self.config["footer"]:
            self.set_font("times", size=8)
            for line in self.config["footer"]["text"]:
                self.cell(
                    0,
                    None,
                    line.upper(),
                    new_x="LMARGIN",
                    new_y="NEXT",
                    align="C",
                    markdown=True,
                )

    def print_client_details(
        self,
        client_name: str,
        client_address: str | None = None,
        client_phone: str | None = None,
        client_email: str | None = None,
    ):
        """Print the client's details in the PDF."""
        self.set_font("times", size=10)
        self.multi_cell(
            0,
            None,
            (
                "**ISSUED TO:**"
                f"\n{client_name}"
                f"{'\n' + client_address if client_address else ''}"
                f"{'\nPhone: ' + client_phone if client_phone else ''}"
                f"{'\nEmail: ' + client_email if client_email else ''}"
            ),
            align="L",
            markdown=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )

    def print_metadata(
        self,
        metadata: Sequence[tuple[str, str]],
    ):
        """Print the metadata in the PDF."""
        self.set_font("times", size=10)

        needed_gap = 0.0
        for _, value in metadata:
            needed_gap = max(needed_gap, self.get_string_width(value, markdown=True))

        for label, value in metadata:
            self.cell(
                self.epw - needed_gap - 2,
                None,
                label.upper() + ":",
                new_x="END",
                new_y="LAST",
                align="R",
                markdown=True,
            )
            self.cell(
                0,
                None,
                value,
                new_x="LMARGIN",
                new_y="NEXT",
                align="R",
                markdown=True,
            )

    def print_invoice_header(self, invoice_header: Mapping[str, str]):
        """Print the invoice header in the PDF."""
        section_start = self.get_y()

        self.print_client_details(
            client_name=invoice_header["client"],
            client_address=invoice_header.get("client_address"),
            client_phone=invoice_header.get("client_phone"),
            client_email=invoice_header.get("client_email"),
        )

        section_end = self.get_y()

        self.set_y(section_start)

        self.print_metadata(
            metadata=[
                ("**Invoice No**", f"**{invoice_header['number']}**"),
                ("Date", invoice_header["date"]),
                ("Due Date", invoice_header["due date"]),
            ]
        )

        self.set_y(max(self.get_y(), section_end))
        self.ln(20)

    def print_receipt_header(self, receipt_header: Mapping[str, str]):
        """Print the invoice header in the PDF."""
        section_start = self.get_y()

        self.print_client_details(
            client_name=receipt_header["client"],
            client_address=receipt_header.get("client_address"),
            client_phone=receipt_header.get("client_phone"),
            client_email=receipt_header.get("client_email"),
        )

        section_end = self.get_y()

        self.set_y(section_start)

        self.print_metadata(
            metadata=[
                ("**Receipt No**", f"**{receipt_header['number']}**"),
                ("Date", receipt_header["date"]),
            ]
        )

        self.set_y(max(self.get_y(), section_end))
        self.ln(20)

    def get_upi_link(self, invoice_data: Mapping[str, Any]) -> str | None:
        """Generate a UPI link from the configuration."""
        payment_config = self.config.get("payment", {})
        upi_config = payment_config.get("upi", {})

        upi_id = upi_config.get("upi-id")
        if not upi_id:
            logger.warning("UPI ID is not configured. Skipping UPI link generation.")
            return None

        note = upi_config.get("transaction-note", "").replace(
            "{INVOICE_NUMBER}", invoice_data.get("number", "")
        )
        payee_name = upi_config.get(
            "payee_name", self.config.get("seller", {}).get("name", "")
        )

        amount = invoice_data.get("total")
        currency = payment_config.get("currency", "INR")

        if amount is None or not upi_config.get("include-amount", False):
            return f"upi://pay?pa={upi_id}&pn={payee_name}&cu={currency}&tn={note}"

        return (
            f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&cu={currency}&tn={note}"
        )

    def print_invoice_payment_details(self, invoice_data: Mapping[str, Any]):
        """Print payment details in the PDF."""
        payment_config = self.config.get("payment", {})
        if not payment_config:
            logger.warning(
                "Payment configuration is missing. Skipping payment details."
            )
            return

        self.set_font("times", size=10, style="B")

        if "payment-methods-text" in payment_config:
            self.cell(
                0,
                None,
                payment_config.get("payment-methods-text").upper(),
                new_x="LMARGIN",
                new_y="NEXT",
                align="L",
            )

        if "upi" in payment_config:
            upi_config: Mapping[str, Any] = payment_config["upi"]
            upi_link = self.get_upi_link(invoice_data)
            if not upi_link:
                logger.warning("UPI link could not be generated. Skipping UPI section.")
                return
            qr = qrcode.QRCode()
            qr.add_data(upi_link)
            img = qr.make_image()

            self.image(
                img.get_image(),
                w=30,
                h=30,
                link=upi_link if upi_config.get("include-link", False) else "",
            )

            if "bottom-note" in payment_config.get("upi", {}):
                self.cell(
                    0,
                    text=payment_config["upi"]["bottom-note"],
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

    def print_receipt_payment_details(self, receipt_data: Mapping[str, Any]):
        """Print payment details in the PDF."""
        payment_mode = receipt_data.get("payment mode", "cash").upper()
        self.set_font("times", size=10, style="B")
        self.cell(
            0,
            None,
            f"PAYMENT MODE: {payment_mode}",
            new_x="LMARGIN",
            new_y="NEXT",
            align="L",
        )
        self.set_font("times", size=10)
        if "reference" in receipt_data:
            reference = receipt_data["reference"]
            if reference:
                self.cell(
                    0,
                    None,
                    f"Reference #: {reference}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                    align="L",
                )

    def print_signature(self) -> None:
        """Print signature section in the PDF."""
        self.set_font("times", size=10, style="B")

        if "signature" in self.config:
            logger.info("Printing signature section.")

            signature_config = self.config["signature"]

            if "prefix" in signature_config:
                self.cell(
                    0,
                    None,
                    signature_config["prefix"].upper(),
                    new_x="LMARGIN",
                    new_y="NEXT",
                    align="R",
                )

            self.set_font("Helvetica", size=12, style="BU")

            if "text" in signature_config:
                self.ln(10)
                self.multi_cell(
                    0,
                    None,
                    signature_config["text"].upper(),
                    new_x="LMARGIN",
                    new_y="NEXT",
                    align="R",
                    markdown=True,
                )

    def print_cover_page(self, details: Mapping[str, Any]) -> None:
        """Print a cover page with details."""
        self.add_page(format="A4")
        self.set_font("Helvetica", size=16, style="B")
        fill_color = self.config.get("invoice", {}).get("style-color")
        self.set_fill_color(fill_color)
        self.cell(
            0,
            15,
            text=details["title"].upper(),
            new_x="LMARGIN",
            new_y="NEXT",
            align="C",
            fill=True,
        )
        self.ln(5)

        if details.get("subtitle"):
            self.set_font("Helvetica", size=12, style="I")
            self.cell(
                0,
                text=details["subtitle"].upper(),
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
            )
            self.ln(10)

        self.set_font("Helvetica", size=10)

        self.cell(0, text=details["date"], new_x="LMARGIN", new_y="NEXT", align="R")

        self.ln(10)

        self.set_font("Helvetica", size=12)
        number_font = FontFace(size_pt=36, emphasis="B")
        self.set_fill_color(0)

        with self.table(
            text_align=("L", "J"),
            padding=8,
            first_row_as_headings=False,
            cell_fill_mode="ROWS",
            borders_layout="NONE",
            cell_fill_color=fill_color,
            col_widths=(12, 20),
            width=int(self.epw) - 20,
        ) as table:
            for key, value in details.get("stats", {}).items():
                if isinstance(value, (int, Decimal)):
                    value = format_number(value)
                row = table.row()
                row.cell(value, style=number_font)
                row.cell(key)


def match_payments(
    invoices: Sequence[Mapping[str, Any]], receipts: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match payments from receipts to invoices.

    Returns two lists:
        - matched_payments: List of receipts with matched invoices.
        - unmatched_invoices: List of invoices that were not fully paid.
    """
    if not invoices or not receipts:
        logger.warning("No invoices or receipts to match.")
        return ([], [])

    unmatched_invoices = []
    matched_payments = []

    for invoice in invoices:
        invoice_number = invoice.get("number")
        if not invoice_number:
            logger.warning("Invoice without number found. Skipping.")
            continue

        invoice_amount = invoice.get("total", 0)
        unmatched_invoices.append(
            {
                "number": invoice_number,
                "balance": invoice_amount,
            }
        )

    for receipt in receipts:
        receipt_number = receipt.get("number")
        receipt_amount = receipt.get("amount", 0)
        receipt_balance = receipt_amount

        matches = []

        while receipt_balance > 0 and unmatched_invoices:
            invoice = unmatched_invoices[0]
            invoice_number = invoice["number"]
            invoice_balance = invoice["balance"]

            if receipt_balance >= invoice_balance:
                matches.append({"invoice": invoice_number, "amount": invoice_balance})
                receipt_balance -= invoice_balance
                unmatched_invoices.pop(0)
            else:
                matches.append({"invoice": invoice_number, "amount": receipt_balance})
                invoice["balance"] -= receipt_balance
                receipt_balance = 0

        if receipt_balance > 0:
            matches.append({"invoice": None, "amount": receipt_balance})

        matched_payments.append(
            {
                "receipt": receipt_number,
                "invoices": matches,
            }
        )

    return (matched_payments, unmatched_invoices)


def format_number(value: Decimal | int) -> str:
    """Format a number to display in summaries."""
    if value > 1_00_000:
        return f"{value / 1_00_000:.2f}L"
    elif value > 1_000:
        return f"{value / 1_000:.2f}K"
    elif isinstance(value, Decimal):
        return f"{value:.2f}"
    else:
        return str(value)
