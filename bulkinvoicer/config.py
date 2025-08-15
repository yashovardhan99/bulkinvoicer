"""Configuration for the bulkinvoicer application."""

import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, FilePath, field_validator


class _SellerConfig(BaseModel):
    """Configuration settings for the seller."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=50)
    tagline: str | None = Field(default=None, max_length=100)


class _InvoiceConfig(BaseModel):
    """Configuration settings for invoices."""

    model_config = ConfigDict(frozen=True)

    decimals: int = Field(default=2, ge=0, le=6)
    """Number of decimal places for invoice amounts."""

    show_subtotal: bool = Field(default=True, alias="show-subtotal")
    """Whether to show the subtotal in the invoice."""

    date_format: str = Field(default="%Y-%m-%d", alias="date-format")
    """Format for displaying dates in the invoice."""

    tax_columns: list[str] = Field(default=[], alias="tax-columns")
    """List of tax columns to include in the invoice, if any."""

    discount_column: str | None = Field(default=None, alias="discount-column")
    """Column name for discounts in the invoice, if applicable."""

    style_color: str = Field(
        default="#FFFFFF",
        alias="style-color",
        pattern=r"^#([A-Fa-f0-9]{8}|[A-Fa-f0-9]{4}|[A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$",
    )
    """Color used for styling the invoice, in hex format."""


class _ReceiptConfig(BaseModel):
    """Configuration settings for receipts."""

    model_config = ConfigDict(frozen=True)

    decimals: int = Field(default=2, ge=0, le=6)
    """Number of decimal places for receipt amounts."""

    date_format: str = Field(default="%Y-%m-%d", alias="date-format")
    """Format for displaying dates in the receipt."""

    style_color: str = Field(
        default="#FFFFFF",
        alias="style-color",
        pattern=r"^#([A-Fa-f0-9]{8}|[A-Fa-f0-9]{4}|[A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$",
    )
    """Color used for styling the receipt, in hex format."""


class _SignatureConfig(BaseModel):
    """Configuration settings for signatures."""

    model_config = ConfigDict(frozen=True)

    prefix: str | None = Field(default=None, max_length=50)
    """Prefix for the signature, if any."""

    text: str | None = Field(default=None, max_length=50)
    """Text for the signature, if any."""


class _UPIConfig(BaseModel):
    """Configuration settings for UPI payments."""

    model_config = ConfigDict(frozen=True)

    upi_id: str = Field(
        alias="upi-id", pattern=r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$"
    )
    """UPI ID for receiving payments."""

    payee_name: str | None = Field(default=None, max_length=50, alias="payee-name")
    """Name of the payee for UPI payments."""

    include_amount: bool = Field(default=True, alias="include-amount")
    """Whether to include the amount in the UPI payment request."""

    include_link: bool = Field(default=False, alias="include-link")
    """Whether to include a payment link in the QR code image."""

    transaction_note: str = Field(default="", max_length=50, alias="transaction-note")
    """Transaction note for the UPI payment request."""

    bottom_note: str | None = Field(default=None, max_length=50, alias="bottom-note")
    """Note to display at the bottom of the UPI QR code image, if any."""


class _PaymentConfig(BaseModel):
    """Configuration settings for payment methods."""

    model_config = ConfigDict(frozen=True)

    upi: _UPIConfig | None = Field(default=None)
    """Configuration for UPI payments, if applicable."""

    currency: Literal["INR", "USD"] | str = Field(
        default="INR",
        alias="currency",
        min_length=1,
    )
    """Currency for the payment methods, default is INR."""

    payment_methods_text: str | None = Field(
        default=None,
        alias="payment-methods-text",
        max_length=50,
    )


class _FooterConfig(BaseModel):
    """Configuration settings for the footer."""

    model_config = ConfigDict(frozen=True)

    text: str | None = Field(
        default=None,
        alias="text",
    )
    """Text to display in the footer, if any."""


class _ExcelConfig(BaseModel):
    """Configuration settings for Excel export."""

    model_config = ConfigDict(frozen=True)

    filepath: FilePath


class _OutputConfig(BaseModel):
    """Configuration settings for output formats."""

    model_config = ConfigDict(frozen=True)

    path: str
    """Path to save the output files."""

    type: Literal["combined", "clients", "individual"]

    include_summary: bool = Field(default=False, alias="include-summary")

    start_date: datetime.date | None = Field(default=None, alias="start-date")
    """Start date for filtering invoices or receipts."""

    end_date: datetime.date | None = Field(default=None, alias="end-date")
    """End date for filtering invoices or receipts."""


class Config(BaseModel):
    """Configuration settings for the bulkinvoicer application."""

    model_config = ConfigDict(frozen=True)

    seller: _SellerConfig
    """Configuration for the seller."""

    invoice: _InvoiceConfig = _InvoiceConfig()
    """Configuration for invoices."""

    receipt: _ReceiptConfig = _ReceiptConfig()
    """Configuration for receipts."""

    signature: _SignatureConfig | None = None
    """Configuration for signatures."""

    payment: _PaymentConfig = _PaymentConfig()
    """Configuration for payment methods."""

    footer: _FooterConfig = _FooterConfig()
    """Configuration for the footer."""

    excel: _ExcelConfig
    """Configuration for Excel export."""

    output: dict[str, _OutputConfig]
    """Configuration for output formats."""

    @field_validator("output", mode="after")
    @classmethod
    def validate_output(cls, v: dict[str, _OutputConfig]) -> dict[str, _OutputConfig]:
        """Ensure that the output configuration contains at least one entry."""
        if not v:
            raise ValueError("At least one output configuration must be provided.")
        return v
