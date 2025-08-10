"""Common utility functions for the Bulkinvoicer application."""

from decimal import Decimal
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
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

        logger.info("Adding fonts.")

        fonts_folder = Path(__file__).parent.parent / "fonts"

        self.add_font("Noto Sans", "", fonts_folder / "NotoSans-Regular.ttf")
        self.add_font("Noto Sans", "B", fonts_folder / "NotoSans-Bold.ttf")
        self.add_font("Noto Sans", "I", fonts_folder / "NotoSans-Italic.ttf")
        self.add_font("Noto Sans", "BI", fonts_folder / "NotoSans-BoldItalic.ttf")

        self.add_font("Noto Sans Mono", "", fonts_folder / "NotoSansMono-Regular.ttf")
        self.add_font("Noto Sans Mono", "B", fonts_folder / "NotoSansMono-Bold.ttf")

        self.add_font("Noto Serif", "", fonts_folder / "NotoSerif-Regular.ttf")
        self.add_font("Noto Serif", "B", fonts_folder / "NotoSerif-Bold.ttf")
        self.add_font("Noto Serif", "I", fonts_folder / "NotoSerif-Italic.ttf")
        self.add_font("Noto Serif", "BI", fonts_folder / "NotoSerif-BoldItalic.ttf")

        self.header_font = FontFace(family="Noto Sans")
        self.regular_font = FontFace(family="Noto Serif")
        self.numbers_font = FontFace(family="Noto Sans Mono")

        self.set_text_shaping(True)

        self.config = config
        self.set_author(config["seller"]["name"])
        self.set_creator("Bulkinvoicer")
        self.set_lang("en-IN")
        self.cover_page = cover_page

    def header(self) -> None:
        """Define the header for the PDF."""
        self.set_font(self.header_font.family, size=16, style="B")
        self.cell(
            0,
            None,
            text=self.config["seller"]["name"].upper(),
            new_x="LMARGIN",
            new_y="NEXT",
            align="C",
            markdown=True,
        )
        if "tagline" in self.config["seller"]:
            self.set_font(self.header_font.family, size=8, style="I")
            self.cell(
                0,
                None,
                text=self.config["seller"]["tagline"],
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
                markdown=True,
            )

        if self.cover_page and self.page_no() == 1:
            logger.info("Leaving less header gap for cover page.")
            self.ln(10)
        else:
            self.ln(20)

    def footer(self) -> None:
        """Define the footer for the PDF."""
        if self.cover_page and self.page_no() == 1:
            logger.info("Skipping footer for cover page.")
            return

        if "footer" in self.config and "text" in self.config["footer"]:
            self.set_font(self.regular_font.family, size=8)
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
        self.set_font(self.regular_font.family, size=10)
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
        needed_gap = 0.0

        for _, value in metadata:
            needed_gap = max(needed_gap, self.get_string_width(value, markdown=True))

        for label, value in metadata:
            self.set_font(self.regular_font.family, size=10)
            self.cell(
                self.epw - needed_gap - 2,
                None,
                label.upper() + ": ",
                new_x="END",
                new_y="LAST",
                align="R",
                markdown=True,
            )
            self.set_font(self.numbers_font.family, size=10)
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
            client_name=invoice_header["client_display_name"],
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
            client_name=receipt_header["client_display_name"],
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

        self.set_font(self.regular_font.family, size=10, style="B")

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
        self.set_font(self.regular_font.family, size=10, style="B")
        self.cell(
            0,
            None,
            f"PAYMENT MODE: {payment_mode}",
            new_x="LMARGIN",
            new_y="NEXT",
            align="L",
        )
        if "reference" in receipt_data:
            reference = receipt_data["reference"]
            if reference:
                self.set_font(self.regular_font.family, size=10)
                self.cell(text="Reference #: ")
                self.set_font(self.numbers_font.family, size=10)
                self.cell(
                    text=reference,
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

    def print_signature(self) -> None:
        """Print signature section in the PDF."""
        if "signature" in self.config:
            logger.info("Printing signature section.")

            signature_config = self.config["signature"]

            if "prefix" in signature_config:
                self.set_font(self.regular_font.family, size=10, style="B")
                self.cell(
                    0,
                    None,
                    signature_config["prefix"].upper(),
                    new_x="LMARGIN",
                    new_y="NEXT",
                    align="R",
                )

            if "text" in signature_config:
                self.set_font(self.header_font.family, size=12, style="BU")
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

    def add_combined_summary(self, details: Mapping[str, Any]) -> None:
        """Print a cover page with details."""
        self.add_page(format="A4")

        fill_color = self.config.get("invoice", {}).get("style-color")
        currency = self.config.get("payment", {}).get("currency", "INR")

        # Header section

        logger.info("Printing header section for summary.")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Details: {details}")

        self.set_font(self.header_font.family, size=18, style="B")
        self.cell(
            0,
            12,
            text="Invoices and Receipts Summary",
            new_x="LMARGIN",
            new_y="NEXT",
            align="C",
        )
        self.set_font(self.header_font.family, size=11)

        if details.get("period"):
            self.cell(
                0,
                text=details["period"],
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
            )
        self.set_font(self.regular_font.family, size=10)
        self.cell(
            0, text=details["generated"], new_x="LMARGIN", new_y="NEXT", align="C"
        )
        self.ln(10)

        logger.info("Printing key figures section.")

        key_figures = details.get("key_figures", [])
        key_figures = filter(None, key_figures)

        self.set_font(self.regular_font.family, size=12, style="B")
        h_space_label = 0.0
        h_space_value = 0.0

        for label, value, *_ in details.get("key_figures", []):
            h_space_label = max(h_space_label, self.get_string_width(label))
            h_space_value = max(
                h_space_value,
                self.get_string_width(
                    format_currency(value, currency)
                    if isinstance(value, Decimal)
                    else str(value)
                ),
            )

        with self.table(
            text_align=("LEFT", "RIGHT", "LEFT"),
            first_row_as_headings=False,
            padding=2,
            align="C",
            width=max(int(self.epw * 0.65), 125),
            borders_layout="NONE",
        ) as key_figures_table:
            for label, value, *extra in key_figures:
                row = key_figures_table.row()
                row.cell(label)
                row.cell(
                    text=format_currency(value, currency)
                    if isinstance(value, Decimal)
                    else f"{value:,}",
                    align="R",
                    style=self.numbers_font,
                )
                row.cell(
                    extra[0] if extra else "",
                    style=FontFace.combine(
                        self.regular_font, FontFace(size_pt=10, emphasis="")
                    ),
                )

        self.ln(10)

        status_breakdown = details.get("status_breakdown", [])
        if status_breakdown:
            logger.info("Printing status breakdown.")

            self.set_font(self.header_font.family, size=14, style="B")

            if self.will_page_break(50):
                self.add_page(same=True)

            self.cell(
                0,
                10,
                text="Status Breakdown",
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
            )

            table_header_style = FontFace.combine(
                self.header_font,
                FontFace(size_pt=12, emphasis="B", fill_color=fill_color),
            )
            self.set_font(self.regular_font.family, size=11)

            with self.table(
                text_align=("LEFT", "RIGHT", "RIGHT"),
                headings_style=table_header_style,
                borders_layout="MINIMAL",
                width=int(max(self.epw * 0.5, 100)),
                align="C",
                col_widths=(2, 1, 2),
                padding=2,
            ) as status_table:
                status_table.row(("Status", "Clients", "Amount"))
                for status in status_breakdown:
                    row = status_table.row()
                    row.cell(status["status"])
                    row.cell(str(status["Clients"]), style=self.numbers_font)
                    row.cell(
                        format_currency(status["amount"], currency),
                        style=self.numbers_font,
                    )

        self.ln(10)

        logger.info("Printing client summaries.")
        client_summaries = details.get("client_summaries", [])
        if client_summaries:
            self.set_font(self.header_font.family, size=14, style="B")

            if self.will_page_break(50):
                self.add_page(same=True)

            self.cell(
                0,
                10,
                text="Client-wise Summary",
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
            )

            table_header_style = FontFace.combine(
                self.header_font,
                FontFace(size_pt=12, emphasis="B", fill_color=fill_color),
            )
            self.set_font(self.regular_font.family, size=11)

            with self.table(
                text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"),
                headings_style=table_header_style,
                borders_layout="MINIMAL",
                align="C",
                padding=2,
            ) as client_table:
                client_table.row(
                    (
                        "Client",
                        "Opening Balance",
                        "Invoiced",
                        "Received",
                        "Closing Balance",
                    )
                )
                for client in client_summaries:
                    row = client_table.row()
                    row.cell(client["client_display_name"] or client["client"])
                    row.cell(
                        format_currency(client["opening_balance"], currency),
                        style=self.numbers_font,
                    )
                    row.cell(
                        format_currency(client["invoice_total"], currency),
                        style=self.numbers_font,
                    )
                    row.cell(
                        format_currency(client["receipt_total"], currency),
                        style=self.numbers_font,
                    )
                    row.cell(
                        format_currency(client["closing_balance"], currency),
                        style=self.numbers_font,
                    )

        self.ln(10)

        logger.info("Printing monthly summary.")
        monthly_summary = details.get("monthly_summary", [])
        if monthly_summary:
            self.set_font(self.header_font.family, size=14, style="B")

            if self.will_page_break(50):
                self.add_page(same=True)

            self.cell(
                0,
                10,
                text="Monthly Summary",
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
            )

            table_header_style = FontFace.combine(
                self.header_font,
                FontFace(size_pt=12, emphasis="B", fill_color=fill_color),
            )
            self.set_font(self.regular_font.family, size=11)

            with self.table(
                text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"),
                headings_style=table_header_style,
                borders_layout="MINIMAL",
                align="C",
                padding=2,
            ) as monthly_table:
                monthly_table.row(
                    (
                        "Month",
                        "Opening Balance",
                        "Invoiced",
                        "Received",
                        "Closing Balance",
                    )
                )
                for month in monthly_summary:
                    row = monthly_table.row()
                    row.cell(f"{month['sort_date'].strftime('%b %Y')}")
                    row.cell(
                        format_currency(month["open"], currency),
                        style=self.numbers_font,
                    )
                    row.cell(
                        format_currency(month["invoiced"], currency),
                        style=self.numbers_font,
                    )
                    row.cell(
                        format_currency(month["received"], currency),
                        style=self.numbers_font,
                    )
                    row.cell(
                        format_currency(month["balance"], currency),
                        style=self.numbers_font,
                    )

        # End of summary
        self.ln(20)


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


def format_currency(value: Decimal, currency: str = "INR") -> str:
    """Format a Decimal value as currency."""
    if value is None:
        return format_currency(Decimal(), currency)
    if not isinstance(value, Decimal):
        raise TypeError("Value must be a Decimal instance.")

    currency_symbol = {
        "INR": "₹",
        "USD": "$",
    }.get(currency)

    if currency_symbol:
        return f"{currency_symbol}{value:>12,}"
    else:
        return f"{value:>12,} {currency}"
