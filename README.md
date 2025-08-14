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

```bash
pip install git+https://github.com/yashovardhan99/bulkinvoicer.git#egg=bulkinvoicer
```

## 🛠️ Usage

1. Prepare your invoice data in an Excel file (use the same format as given in `sample.xlsx`).
2. Create a `config.toml` file to define your preferences.
3. Run the command `incoiver` to generate invoices and summaries.

Alternatively, you can run it directly using pipx:

```bash
pipx run --spec git+https://github.com/yashovardhan99/bulkinvoicer.git invoicer
```

You can find a sample `config.toml` file at [sample.config.toml](sample.config.toml)

## 📄 Documentation

Coming Soon!

## ⚒️ Work in progress

This project is a work in progress. The public API is still in development and unstable.

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
