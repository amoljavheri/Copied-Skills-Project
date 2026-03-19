import pdfplumber
import json
import sys

# Force UTF-8 output to handle special characters
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"C:\Users\amolj\Downloads\E_TRADE Financial — Portfolios PositionsMasked.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    for i, page in enumerate(pdf.pages):
        print(f"\n=== PAGE {i+1} ===")
        text = page.extract_text()
        if text:
            print(text)
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"\n--- TABLE {j+1} ---")
            for row in table:
                print(row)
