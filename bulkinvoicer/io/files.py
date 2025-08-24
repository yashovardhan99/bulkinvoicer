"""Module for writing files."""


def write_pdf(path: str, pdfBytes: bytearray):
    """Write PDF bytes to a file."""
    with open(path, "wb") as f:
        f.write(pdfBytes)
