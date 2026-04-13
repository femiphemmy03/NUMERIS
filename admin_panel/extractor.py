"""
admin_panel/extractor.py

Runs PDF extraction inline (synchronously) when an admin uploads a PDF.
Saves results to both data/processed/ AND the database.
"""
import os
import re
import csv as csv_module
from pathlib import Path
from datetime import datetime

import pdfplumber
import pandas as pd
from django.conf import settings
from django.utils import timezone

from financials.models import Company, Filing, Metric
from financials.data_service import (
    COMPANY_NAME_MAP, FILENAME_OVERRIDES, METRIC_PATTERNS,
    _identify_company, _detect_period, _best_metric_line
)

FINANCIAL_KEYWORDS = [
    "revenue", "turnover", "gross", "profit", "loss", "tax",
    "assets", "liabilities", "equity", "eps", "shares", "income",
    "earnings per share", "dividend", "finance", "interest",
]


def extract_and_save(filing_obj):
    """
    Given a Filing model instance with a pdf_file attached,
    run extraction and save all results to DB + data/processed/.
    Updates filing.status as it goes.
    """
    from financials.models import Filing as FilingModel

    filing_obj.status = 'processing'
    filing_obj.save(update_fields=['status'])

    pdf_path = Path(filing_obj.pdf_file.path)
    stem = pdf_path.stem
    processed_dir = Path(settings.DATA_PROCESSED_DIR)
    processed_dir.mkdir(parents=True, exist_ok=True)

    try:
        text_lines = []
        tables_found = 0

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        line = line.strip()
                        if line and any(kw in line.lower() for kw in FINANCIAL_KEYWORDS):
                            text_lines.append(line)

                # Extract tables → CSV
                tables = page.extract_tables()
                if tables:
                    tables_found += len(tables)
                    for i, table in enumerate(tables):
                        if table and len(table) > 0:
                            df = pd.DataFrame(table)
                            df = df.dropna(how='all').dropna(axis=1, how='all')
                            if not df.empty:
                                csv_path = processed_dir / f"{stem}_page{page_num}_table{i+1}.csv"
                                df.to_csv(csv_path, index=False)

        # Deduplicate and save financial lines
        seen = set()
        deduped = []
        for line in text_lines:
            key = line.lower().strip()
            if key not in seen:
                seen.add(key)
                deduped.append(line)

        txt_path = processed_dir / f"{stem}_financial_lines.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(deduped))

        # Parse metrics and save to DB
        _save_metrics_to_db(filing_obj, deduped)

        filing_obj.status = 'done'
        filing_obj.processed_at = timezone.now()
        filing_obj.save(update_fields=['status', 'processed_at'])

        # Clear the data_service cache so dashboard reflects new data
        try:
            from financials.data_service import _get_index
            _get_index.cache_clear()
        except Exception:
            pass

        return True, f"Extracted {len(deduped)} financial lines and {tables_found} tables."

    except Exception as e:
        filing_obj.status = 'failed'
        filing_obj.error_log = str(e)
        filing_obj.save(update_fields=['status', 'error_log'])
        return False, str(e)


def _save_metrics_to_db(filing_obj, lines):
    """Parse financial metrics from extracted lines and store in DB."""
    from financials.data_service import _best_metric_line

    Metric.objects.filter(filing=filing_obj).delete()

    for key, label, patterns in METRIC_PATTERNS:
        _, nums = _best_metric_line(lines, patterns)
        if nums:
            cur = nums[0] * 1_000   # files are in N'000
            prv = nums[1] * 1_000 if len(nums) > 1 else None
            Metric.objects.create(
                filing=filing_obj,
                key=key,
                label=label,
                current_value=cur,
                prior_value=prv,
            )


def get_or_create_company_from_filename(pdf_filename):
    """
    Identify company from PDF filename and get/create Company DB record.
    Returns (Company instance, period_dict) or (None, None) if unrecognised.
    """
    stem = Path(pdf_filename).stem
    identity = _identify_company(stem)
    if identity is None:
        return None, None
    ticker, name, sector = identity
    period = _detect_period(stem)
    company, _ = Company.objects.get_or_create(
        ticker=ticker,
        defaults={'name': name, 'sector': sector}
    )
    return company, period
