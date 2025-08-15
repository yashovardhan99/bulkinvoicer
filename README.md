# BulkInvoicer

BulkInvoicer is a simple, offline-friendly CLI tool that helps freelancers and small businesses manage invoices and receipts in bulk using Excel. It generates professional-looking invoices, client summaries, and account statements—all from a single spreadsheet.

## ✨ Features

- 📁 **Excel-Based Workflow** – Use your existing spreadsheet to manage invoices.
- 🖨️ **Beautiful Invoice Generation** – Create printable invoices with custom styling.
- 🎨 **Fully Customisable Templates** – Modify colours, headers, footers, and fields.
- 📱 **UPI QR Code Support** – Automatically embed UPI QR codes for instant payments.
- 📊 **Summary Pages** – Generate overall and client-specific summaries.
- 📄 **PDF Output Options** – Export combined, client-wise, or individual invoice PDFs.
- 🔄 **Auto-Matching Receipts** – Match invoices with receipts and track advance payments.
- ⚙️ **Simple TOML Configuration** – Customise output types and preferences easily.
- 🔒 **Offline & Open Source** – Works entirely offline and is fully open-source.

## 📦 Installation

You can get BulkInvoicer from both [PyPi](https://pypi.org/project/bulkinvoicer/) and GitHub:

### PyPi

Just run:
```bash
pip install bulkinvoicer
```

### GitHub

You can also get BulkInvoicer directly from GitHub:
```bash
pip install git+https://github.com/yashovardhan99/bulkinvoicer.git#egg=bulkinvoicer
```

## 🛠️ Usage

1. Prepare your invoice data in an Excel file (use the same format as given in `sample.xlsx`).
2. Create a `config.toml` file to define your preferences.
3. Run the CLI command `incoiver` to generate invoices and summaries.

Alternatively, you can run it directly using pipx:

```bash
pipx run bulkinvoicer
```

You can find a sample `config.toml` file at [sample.config.toml](sample.config.toml)

## ⚒️ Changes

All changes to this project are tracked in our [CHANGELOG](CHANGELOG.md). If you create a pull request, please include a summary of your changes in this file.

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
