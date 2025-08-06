"""Generate a simple invoice PDF using FPDF and QR code for payment."""

import qrcode
from fpdf import FPDF, FontFace
from textwrap import dedent

pdf = FPDF()
pdf.add_page(format="A4")

# Invoice Header
pdf.set_font("courier", size=16, style="B")
pdf.cell(0, text="Seller Name".upper(), new_x="LMARGIN", new_y="NEXT", align="C")

pdf.set_font("helvetica", size=8, style="I")
pdf.cell(0, text="Tagline", new_x="LMARGIN", new_y="NEXT", align="C")

pdf.ln(20)  # Line break for spacing

section_y = pdf.get_y()

pdf.set_font("times", size=10)

# Issued To:
pdf.multi_cell(
    0,
    None,
    dedent("""\
    **ISSUED TO:**
    John Doe
    1234 Elm Street
    City, State, ZIP
    Phone: (123) 456-7890"""),
    align="L",
    markdown=True,
    new_x="LMARGIN",
    new_y="TOP",
)

section_end_y = pdf.get_y()

# Invoice Details

INVOICE_DATA = (
    ("**Invoice No**", "**INV-2025-001**"),
    ("Date", "2025-01-01"),
    ("Due Date", "2025-01-15"),
)

needed_gap = 0.0
for _, value in INVOICE_DATA:
    needed_gap = max(needed_gap, pdf.get_string_width(value, markdown=True))

for label, value in INVOICE_DATA:
    pdf.cell(
        pdf.epw - needed_gap - 2,
        None,
        label.upper() + ":",
        new_x="END",
        new_y="LAST",
        align="R",
        markdown=True,
    )
    pdf.cell(
        0,
        None,
        value,
        new_x="LMARGIN",
        new_y="NEXT",
        align="R",
        markdown=True,
    )


pdf.set_y(max(pdf.get_y(), section_end_y))

pdf.ln(20)  # Line break for spacing

INVOICE_ITEMS = (
    ("Description".upper(), "Unit Price".upper(), "Qty".upper(), "Total".upper()),
    ("Service Provided", "100.00", "2", "200.00"),
)

# Invoice Table
headings_style = FontFace(emphasis="BOLD", fill_color=(248, 230, 229))
with pdf.table(
    text_align=("LEFT", "CENTER", "CENTER", "RIGHT"),
    borders_layout="NONE",
    padding=2,
    headings_style=headings_style,
) as table:
    for invoice_row in INVOICE_ITEMS:
        row = table.row()
        for item in invoice_row:
            row.cell(item)

    table.row()
    subtotal_row = table.row(style=FontFace(emphasis="BOLD"))
    subtotal_row.cell("Subtotal", colspan=3, align="LEFT")
    subtotal_row.cell("200.00")

    discount_row = table.row()
    discount_row.cell("Discount", colspan=3, align="RIGHT")
    discount_row.cell("0.00")

    total_row = table.row(style=headings_style)
    total_row.cell("Total".upper(), colspan=3, align="RIGHT")
    total_row.cell("200.00")


pdf.ln(20)

pdf.set_font("times", size=10, style="B")

pdf.cell(
    0,
    None,
    "Pay via UPI/Cash".upper(),
    new_x="LMARGIN",
    new_y="TOP",
    align="L",
)

pdf.cell(
    0,
    None,
    "Thank you!".upper(),
    new_x="LMARGIN",
    new_y="NEXT",
    align="R",
)

data = "upi://pay?pa=sample@upi&am=100&cu=INR&tn=Payment%for%invoice%INV-2025-001"
img = qrcode.make(data)

pdf.image(img.get_image(), w=30, h=30, link=data)
# pdf.set_x(pdf.w - pdf.r_margin - 15)
pdf.cell(
    0,
    text="Scan the above QR code to pay via UPI",
    new_x="LMARGIN",
    new_y="NEXT",
)

pdf.ln(20)
pdf.set_font("times", size=8, style="I")

pdf.cell(
    0,
    None,
    "All amounts in INR.".upper(),
    new_x="LMARGIN",
    new_y="NEXT",
    align="C",
)

pdf.cell(
    0,
    None,
    "This is a computer-generated document and does not require a signature.".upper(),
    new_x="LMARGIN",
    new_y="NEXT",
    align="C",
)

pdf.output("invoice.pdf")
