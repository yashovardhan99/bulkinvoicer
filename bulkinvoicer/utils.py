"""Common utility functions for the Bulkinvoicer application."""

import logging
from typing import Any
from collections.abc import Mapping, Sequence
from fpdf import FPDF
import qrcode

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
    ):
        """Initialize the PDF with optional configuration."""
        super().__init__(orientation, unit, format, font_cache_dir)
        self.config = config
        self.set_author(config["seller"]["name"])
        self.set_creator("Bulkinvoicer")
        self.set_lang("en-IN")

    def header(self) -> None:
        """Define the header for the PDF."""
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
        upi_config = self.config.get("payment", {}).get("upi", {})

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
        currency = upi_config.get("currency", "INR")

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
            img = qrcode.make(upi_link)

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
