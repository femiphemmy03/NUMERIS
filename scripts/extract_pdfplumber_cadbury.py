# scripts/extract_pdfplumber_cadbury.py
# Alternative extraction using pdfplumber (better for complex financial PDFs)

import pdfplumber
import os
import re

pdf_path = os.path.join("data", "raw", "cadbury_q3_2025.pdf")

print(f"Checking file exists: {os.path.exists(pdf_path)}")
if not os.path.exists(pdf_path):
    print("ERROR: PDF file not found!")
    exit(1)

print("Starting pdfplumber extraction...")

try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"PDF has {len(pdf.pages)} pages total.")

        # Focus on pages 6-15 (adjust if needed)
        start_page = 6
        end_page = min(15, len(pdf.pages))

        print(f"Processing pages {start_page} to {end_page}...")

        for page_num in range(start_page-1, end_page):  # 0-based index
            page = pdf.pages[page_num]
            print(f"\n=== Page {page_num+1} ===")

            # Extract all text (with layout preserved)
            text = page.extract_text(layout=True)
            if text:
                print("Full text excerpt (first 1000 chars):")
                print(text[:1000])
                print("...")

                # Simple keyword search for key lines
                lines = text.split('\n')
                print("\nPotential financial lines (keyword search):")
                for line in lines:
                    if any(kw in line.lower() for kw in ["revenue", "profit", "gross", "assets", "liabilities", "equity", "eps", "shares", "income", "tax"]):
                        print(line.strip())

            # Try table extraction on this page
            tables = page.extract_tables()
            if tables:
                print(f"Found {len(tables)} tables on page {page_num+1}")
                for tbl_idx, table in enumerate(tables):
                    print(f"\nTable {tbl_idx+1} on page {page_num+1}:")
                    for row in table[:10]:  # first 10 rows
                        print(row)
                    print("-" * 80)

            else:
                print("No tables detected on this page.")

except Exception as e:
    print("Extraction failed!")
    print(f"Error: {str(e)}")

print("\nExtraction finished. Look for lines with 'Revenue', 'Profit after tax', 'Total assets', etc.")
