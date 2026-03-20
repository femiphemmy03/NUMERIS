import os
import pdfplumber
import camelot
import pandas as pd

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"

def list_pdfs():
    """List all PDF files in the raw folder."""
    return [f for f in os.listdir(RAW_DIR) if f.endswith(".pdf")]

def extract_text(file_path):
    """Extract text from the first page using pdfplumber."""
    with pdfplumber.open(file_path) as pdf:
        first_page = pdf.pages[0]
        return first_page.extract_text()

def extract_tables(file_path):
    """Extract tables using Camelot."""
    tables = camelot.read_pdf(file_path, pages="all")
    dfs = [t.df for t in tables]
    return dfs

def process_pdf(pdf_file):
    """Process a single PDF and save results to processed folder."""
    file_path = os.path.join(RAW_DIR, pdf_file)
    print(f"Processing {pdf_file}...")

    # Extract text
    text = extract_text(file_path)
    text_out = os.path.join(PROCESSED_DIR, pdf_file.replace(".pdf", "_text.txt"))
    with open(text_out, "w", encoding="utf-8") as f:
        f.write(text or "")

    # Extract tables
    dfs = extract_tables(file_path)
    for i, df in enumerate(dfs):
        table_out = os.path.join(PROCESSED_DIR, pdf_file.replace(".pdf", f"_table{i}.csv"))
        df.to_csv(table_out, index=False)

    print(f"✅ Processed {pdf_file}: text + {len(dfs)} tables saved.")

if __name__ == "__main__":
    pdfs = list_pdfs()
    if not pdfs:
        print("No PDFs found in data/raw.")
    else:
        for pdf in pdfs:
            process_pdf(pdf)
