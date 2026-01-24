# scripts/extract_test_cadbury.py
# Test extraction from Cadbury Q3 2025 PDF with focused pages and better mode handling

import tabula
import os
import pandas as pd

# Path to the PDF (relative to project root)
pdf_path = os.path.join("data", "raw", "cadbury_q3_2025.pdf")

print(f"Checking file exists: {os.path.exists(pdf_path)}")
if not os.path.exists(pdf_path):
    print("ERROR: PDF file not found! Check path and filename.")
    exit(1)

print("Starting table extraction...")

try:
    # Focus only on pages where financial statements usually are (income statement, balance sheet)
    pages_to_extract = "6-15"

    print(f"Extracting tables from pages {pages_to_extract}...")

    # First try stream mode (good for text-based financial tables without thick borders)
    tables = tabula.read_pdf(
        pdf_path,
        pages=pages_to_extract,
        multiple_tables=True,
        stream=True,
        guess=True,          # Try to guess table boundaries
        pandas_options={'header': None}  # No auto header to avoid confusion
    )

    # If no tables found or very few, fallback to lattice mode (better for bordered tables)
    if len(tables) < 3:  # arbitrary threshold — adjust if needed
        print("Few/no tables in stream mode → trying lattice mode...")
        tables = tabula.read_pdf(
            pdf_path,
            pages=pages_to_extract,
            multiple_tables=True,
            lattice=True,
            guess=True,
            pandas_options={'header': None}
        )

    print(f"Found {len(tables)} tables in pages {pages_to_extract} (using {'stream' if 'stream' in str(tables) else 'lattice'} mode).")

    if len(tables) == 0:
        print("No tables detected. Try widening page range or check if PDF is image-based.")
    else:
        for i, df in enumerate(tables):
            print(f"\n--- Table {i+1} ({df.shape[0]} rows, {df.shape[1]} columns) ---")
            
            # Clean up: drop fully empty rows/columns
            df = df.dropna(how='all').dropna(axis=1, how='all')
            
            # Print full table if small, else head + tail
            if len(df) <= 30:
                print(df.to_string(index=False))
            else:
                print("Table too large — showing head + tail:")
                print(df.head(15).to_string(index=False))
                print("\n...\n")
                print(df.tail(10).to_string(index=False))
            
            print("\n" + "="*100 + "\n")

    print("Extraction finished. Look for tables containing 'Revenue', 'Profit', 'Assets', 'Equity', etc.")

except Exception as e:
    print("Extraction failed!")
    print(f"Error details: {str(e)}")
    print("\nCommon fixes:")
    print("- Ensure Java is installed and in PATH (run 'java -version' in terminal)")
    print("- PDF may have complex layout — try different page range (e.g. '5-20')")
    print("- If tables are image-based (scanned), tabula won't work well → need OCR (later step)")
