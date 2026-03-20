# scripts/auto_extract_basic.py
# MVP Automation Phase 1: Scan all PDFs in data/raw/, extract text/tables, save to processed/

import os
import pdfplumber
import pandas as pd
from pathlib import Path
from datetime import datetime

# Paths
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path("data") / "processed"

# Create processed folder if missing
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def extract_from_pdf(pdf_path):
    """Extract text and tables from one PDF"""
    print(f"\nProcessing: {pdf_path.name}")
    results = {"path": str(pdf_path), "timestamp": datetime.now().isoformat(), "text_lines": [], "tables_found": 0}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text
                text = page.extract_text()
                if text:
                    lines = text.split('\n')
                    financial_lines = [line.strip() for line in lines if any(kw in line.lower() for kw in [
                        "revenue", "gross", "profit", "tax", "assets", "liabilities", "equity", "eps", "shares", "income"
                    ])]
                    if financial_lines:
                        print(f"Page {page_num} - Found {len(financial_lines)} financial lines:")
                        for line in financial_lines:
                            print("  " + line)
                        results["text_lines"].extend(financial_lines)

                # Extract tables
                tables = page.extract_tables()
                if tables:
                    results["tables_found"] += len(tables)
                    print(f"Page {page_num} - Found {len(tables)} tables")

                    # Save first table as CSV for debug
                    for i, table in enumerate(tables):
                        if table and len(table) > 0:
                            df = pd.DataFrame(table)
                            csv_path = PROCESSED_DIR / f"{pdf_path.stem}_page{page_num}_table{i+1}.csv"
                            df.to_csv(csv_path, index=False)
                            print(f"  Saved table to {csv_path.name}")

        # Save all extracted financial lines to txt
        if results["text_lines"]:
            txt_path = PROCESSED_DIR / f"{pdf_path.stem}_financial_lines.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(results["text_lines"]))
            print(f"Saved financial lines to {txt_path.name}")

        return results

    except Exception as e:
        print(f"Error processing {pdf_path.name}: {str(e)}")
        return {"path": str(pdf_path), "error": str(e)}

def main():
    print("MVP Auto Extraction - Scanning data/raw/")
    print(f"Raw directory: {RAW_DIR.resolve()}")

    processed_count = 0
    for root, _, files in os.walk(RAW_DIR):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = Path(root) / file
                result = extract_from_pdf(pdf_path)
                processed_count += 1
                print(f"Completed: {pdf_path.name}")

    print(f"\nFinished. Processed {processed_count} PDFs.")
    print(f"Check data/processed/ for extracted text and CSV tables.")

if __name__ == "__main__":
    main()
