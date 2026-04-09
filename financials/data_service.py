"""
numeris/financials/data_service.py  — FULLY AUTOMATED

How it works:
  1. Scans data/processed/ at startup for all *_financial_lines.txt files.
  2. Detects company identity and filing period from each filename.
  3. Parses financial numbers (revenue, PAT, assets, equity, gross profit)
     directly from the extracted text using regex — no hardcoding.
  4. Builds KPI cards, chart trend data, ratios, and signal flags automatically.
  5. Groups all filings per company and exposes them via get_all_companies()
     and get_company_data(ticker).

To add a new company:
  → Just drop its processed files into data/processed/ and restart.
  → If the company name is not in COMPANY_NAME_MAP below, add one line there.

To add a new filing for an existing company:
  → Drop the files in. Nothing else needed.
"""

import os
import re
import csv
from functools import lru_cache
from django.conf import settings


# ─────────────────────────────────────────────────────────────────────────────
# COMPANY IDENTITY MAP
# Maps a keyword (found in the filename, uppercased) to
# (ticker, full_name, sector).
# The list is checked in order — put more specific keywords first.
# Add one entry here when a brand-new company appears.
# ─────────────────────────────────────────────────────────────────────────────
COMPANY_NAME_MAP = [
    # keyword               ticker        full name                               sector
    ("MTN_NIGERIA",        "MTNN",       "MTN Nigeria Communications Plc",       "Telecommunications"),
    ("GUARANTY_TRUST",     "GTCO",       "Guaranty Trust Holding Company Plc",   "Banking"),
    ("CHAMS_HOLDING",      "CHAMS",      "Chams Holding Company Plc",            "Technology"),
    ("NESTLE_NIGERIA",     "NESTLE",     "Nestlé Nigeria Plc",                   "Consumer Goods"),
    ("NESTLE",             "NESTLE",     "Nestlé Nigeria Plc",                   "Consumer Goods"),
    ("ACCESS",             "ACCESS",     "Access Holdings Plc",                  "Banking"),
    ("UBA",                "UBA",        "United Bank for Africa Plc",           "Banking"),
    ("GUINNESS",           "GUINNESS",   "Guinness Nigeria Plc",                 "Consumer Goods"),
    ("DANGSUGAR",          "DANGSUGAR",  "Dangote Sugar Refinery Plc",           "Consumer Goods"),
    ("DANSUGAR",           "DANGSUGAR",  "Dangote Sugar Refinery Plc",           "Consumer Goods"),
    ("CADBURY",            "CADBURY",    "Cadbury Nigeria Plc",                  "Consumer Goods"),
    ("OMATEK",             "OMATEK",     "Omatek Ventures Plc",                  "Technology"),
    ("TRANS",              "TRANSNWEX",  "Trans-Nationwide Express Plc",         "Industrials"),
    ("BERGER",             "BERGER",     "Berger Paints Nigeria Plc",            "Industrials"),
    ("ZENITH",             "ZENITHBANK", "Zenith Bank Plc",                      "Banking"),
    ("STANBIC",            "STANBIC",    "Stanbic IBTC Holdings Plc",            "Banking"),
    ("FBNH",               "FBNH",       "FBN Holdings Plc",                     "Banking"),
    ("FLOURMILL",          "FLOURMILL",  "Flour Mills of Nigeria Plc",           "Consumer Goods"),
    ("BUA_FOODS",          "BUAFOODS",   "BUA Foods Plc",                        "Consumer Goods"),
    ("JAIZ",               "JAIZBANK",   "Jaiz Bank Plc",                        "Banking"),
    ("FIRSTHOLDCO",        "FIRSTHOLDCO","First HoldCo Plc",                     "Banking"),
    ("FIRST_HOLDCO",       "FIRSTHOLDCO","First HoldCo Plc",                     "Banking"),
    ("MULTIVERSE",         "MULTIVERSE", "Multiverse Ventures Plc",              "Technology"),
]

# Filenames whose company cannot be inferred from the name alone.
# Maps exact filename stem (without _financial_lines.txt) → ticker.
FILENAME_OVERRIDES = {
    "audited 2023": "BERGER",
    "audited 2024": "BERGER",
    "q125":         "BERGER",
    "q225":         "BERGER",
    "q325":         "BERGER",
    "q425":         "BERGER",
}

# ─────────────────────────────────────────────────────────────────────────────
# METRIC EXTRACTION PATTERNS
# Each entry: (internal_key, display_label, [regex_patterns])
# Patterns match the beginning of a line (case-insensitive).
# ─────────────────────────────────────────────────────────────────────────────
METRIC_PATTERNS = [
    ("revenue", "Revenue", [
        r"^revenue\b",
        r"^turnover\b",
        r"^gross\s+earnings\b",
        r"^total\s+revenue\b",
    ]),
    ("gross_profit", "Gross Profit", [
        r"^gross\s+profit\b",
        r"^gross\s+profit[/\(]",
    ]),
    ("operating_profit", "Operating Profit", [
        r"^operating\s+profit\b",
        r"^operating\s+profit[/\(]",
    ]),
    ("profit_before_tax", "Profit Before Tax", [
        r"^profit\s+before\s+tax",
        r"^profit\s+before\s+taxation",
        r"^\(loss\)/profit\s+before\s+tax",
        r"^loss\s+before\s+tax",
        r"^profit\s+on\s+continuing\s+operations\s+before",
    ]),
    ("pat", "Profit / (Loss) After Tax", [
        r"^profit\s+for\s+the\s+year\b",
        r"^profit\s+for\s+the\s+period\b",
        r"^loss\s+for\s+the\s+year\b",
        r"^loss\s+for\s+the\s+period\b",
        r"^\(loss\)/profit\s+for\s+the\s+year\b",
        r"^\(loss\)/profit\s+for\s+the\s+period\b",
        r"^profit\s+after\s+tax\b",
        r"^profit\s+after\s+taxation\b",
        r"^\(loss\)/profit\s+after\s+tax",
    ]),
    ("total_assets", "Total Assets", [
        r"^total\s+assets\b",
        r"^total\s+assets\s+and",
    ]),
    ("total_equity", "Total Equity", [
        r"^total\s+equity\b(?!\s+and\s+liab)",
        r"^total\s+equity\s+attributable",
        r"^equity\s+attributable",
    ]),
    ("net_interest_income", "Net Interest Income", [
        r"^net\s+interest\s+income\b",
    ]),
    ("eps", "Earnings Per Share", [
        r"^earnings\s+per\s+share",
        r"^\beps\b",
        r"^basic\s+earnings\s+per\s+share",
    ]),
]


# ─────────────────────────────────────────────────────────────────────────────
# PERIOD DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _detect_period(fname_stem):
    """
    Detect the filing period from a filename stem.
    Returns dict: {quarter, year, period_label, sort_key, filing_month}
    """
    fu = fname_stem.upper()

    # NGX standard: ...QUARTER_5_...FOR_2024_FINANCIAL_STATEMENTS_FEBRUARY_2025
    m = re.search(
        r'QUARTER_(\d+).*?FOR_(\d{4})_FINANCIAL_STATEMENTS_(\w+)_(\d{4})', fu)
    if m:
        q, fy = int(m.group(1)), int(m.group(2))
        month = m.group(3).title()
        label = f"FY {fy} (Audited)" if q == 5 else f"Q{q} {fy}"
        return {"quarter": q, "year": fy, "period_label": label,
                "sort_key": fy * 10 + q, "filing_month": month}

    # YEAR_END format
    m = re.search(r'YEAR_END.*?FOR_(\d{4})', fu)
    if m:
        fy = int(m.group(1))
        return {"quarter": 5, "year": fy, "period_label": f"FY {fy} (Year End)",
                "sort_key": fy * 10 + 5, "filing_month": ""}

    # Named files — extract year then quarter
    year = None
    for pat in [r'20(\d{2})', r'[_\s](\d{2})[_\s]', r'[_\s](\d{2})$']:
        m = re.search(pat, fu)
        if m:
            yr = int(m.group(1))
            year = 2000 + yr if yr < 100 else yr
            break
    if year is None:
        return {"quarter": 0, "year": 0, "period_label": fname_stem,
                "sort_key": 0, "filing_month": ""}

    quarter, period_label, sort_offset = 5, f"FY {year}", 5
    for pat, q, lbl in [
        (r'\bQ1\b|\bq1\b|Q1\s*\d{2}|QUARTER.?1', 1, f"Q1 {year}"),
        (r'\bQ2\b|\bq2\b|Q2\s*\d{2}|QUARTER.?2', 2, f"Q2 {year}"),
        (r'\bQ3\b|\bq3\b|Q3\s*\d{2}|QUARTER.?3', 3, f"Q3 {year}"),
        (r'\bQ4\b|\bq4\b|Q4\s*\d{2}|QUARTER.?4', 4, f"Q4 {year}"),
    ]:
        if re.search(pat, fu):
            quarter, period_label, sort_offset = q, lbl, q
            break
    else:
        if any(w in fu for w in ["AUDIT", "ANNUAL", "FULL", "FY", "YEAR"]):
            period_label = f"FY {year} (Audited)"

    return {"quarter": quarter, "year": year, "period_label": period_label,
            "sort_key": year * 10 + sort_offset, "filing_month": ""}


# ─────────────────────────────────────────────────────────────────────────────
# NUMBER EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def _extract_numbers_from_line(line):
    """
    Extract financial numbers from a line.
    Handles OCR splits ('5 37,527' → 537527) vs note refs ('9 3,358,461' → 3358461).
    Rule: merge single digit + next token ONLY when next token starts with
    exactly 2 digits before its first comma.
    """
    tokens = re.split(r'\s+', line.strip())

    # Drop text label at start
    while tokens and not re.search(r'[\d(]', tokens[0]):
        tokens.pop(0)

    # Merge OCR splits: ['5', '37,527'] → ['537,527']
    # But NOT note refs: ['9', '3,358,461'] stays as-is (3 digits before comma)
    merged = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if re.fullmatch(r'\d{1,2}', tok) and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            if re.match(r'^\d{2},', nxt):   # exactly 2 digits before comma = OCR split
                merged.append(tok + nxt)
                i += 2
                continue
        merged.append(tok)
        i += 1

    results = []
    for tok in merged:
        if re.fullmatch(r'-+', tok):         # skip dash placeholders
            continue
        negative = tok.startswith('(') and tok.endswith(')')
        raw = tok.strip('()').replace(',', '')
        raw = re.sub(r'[^\d.]', '', raw)
        if not raw:
            continue
        if re.fullmatch(r'\d{1,2}', raw):    # skip note references
            continue
        if re.fullmatch(r'\d{1,3}\.\d{1,2}', raw):   # skip percentages
            continue
        try:
            val = float(raw)
            if abs(val) >= 100:
                results.append(-val if negative else val)
                if len(results) == 2:
                    break
        except ValueError:
            pass

    return results


def _best_metric_line(lines, patterns):
    """
    Find the first line matching any of the patterns that also contains numbers.
    Returns (line, [numbers]) or (None, []).
    """
    for line in lines:
        ll = line.lower().strip()
        for pat in patterns:
            if re.match(pat, ll):
                nums = _extract_numbers_from_line(line)
                if nums:
                    return line, nums
    return None, []


# ─────────────────────────────────────────────────────────────────────────────
# DIRECTORY SCAN
# ─────────────────────────────────────────────────────────────────────────────

def _identify_company(fname_stem):
    """Return (ticker, name, sector) or None."""
    override_ticker = FILENAME_OVERRIDES.get(fname_stem.strip())
    if override_ticker:
        for kw, ticker, name, sector in COMPANY_NAME_MAP:
            if ticker == override_ticker:
                return ticker, name, sector

    fu = fname_stem.upper()
    for keyword, ticker, name, sector in COMPANY_NAME_MAP:
        if keyword in fu:
            return ticker, name, sector
    return None


def _scan_processed_dir():
    """
    Scan data/processed/ and build:
      {ticker: {ticker, name, sector, filings: [...]}}
    Each filing has: {stem, period, fin_lines_path, csv_paths}
    """
    processed_dir = settings.DATA_PROCESSED_DIR
    companies = {}

    all_files = sorted(os.listdir(processed_dir))
    fin_line_files = [(f, os.path.join(processed_dir, f))
                      for f in all_files if f.endswith("_financial_lines.txt")]
    csv_files      = [(f, os.path.join(processed_dir, f))
                      for f in all_files if f.endswith(".csv")]

    for fname, fpath in fin_line_files:
        stem     = fname.replace("_financial_lines.txt", "")
        identity = _identify_company(stem)
        if identity is None:
            continue
        ticker, name, sector = identity
        period = _detect_period(stem)

        filing_csvs = [(cf, cp) for cf, cp in csv_files if cf.startswith(stem)]

        if ticker not in companies:
            companies[ticker] = {"ticker": ticker, "name": name,
                                  "sector": sector, "filings": []}

        companies[ticker]["filings"].append({
            "stem":           stem,
            "period":         period,
            "fin_lines_path": fpath,
            "csv_paths":      filing_csvs,
        })

    for t in companies:
        companies[t]["filings"].sort(key=lambda f: f["period"]["sort_key"])

    return companies


# ─────────────────────────────────────────────────────────────────────────────
# METRIC PARSING
# ─────────────────────────────────────────────────────────────────────────────

def _parse_filing_metrics(fin_lines_path):
    try:
        with open(fin_lines_path, encoding="utf-8", errors="replace") as f:
            lines = [l.rstrip() for l in f]
    except Exception:
        return {}

    metrics = {}
    for key, _label, patterns in METRIC_PATTERNS:
        _, nums = _best_metric_line(lines, patterns)
        if nums:
            # Source files are in ₦'000 — multiply by 1,000 to get absolute Naira
            current = nums[0] * 1_000
            prior   = nums[1] * 1_000 if len(nums) > 1 and nums[1] is not None else None
            metrics[key] = (current, prior)

    return metrics
# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _compute_signal_and_flags(trend_data):
    """Auto-generate BUY/HOLD/WATCH/AVOID signal and intelligence flags."""
    flags = []

    def latest(key):
        s = trend_data.get(key, [])
        return s[-1][1] if s else None

    def prior(key):
        s = trend_data.get(key, [])
        return s[-2][1] if len(s) >= 2 else None

    def growth(key):
        l, p = latest(key), prior(key)
        if l is not None and p and p != 0:
            return (l - p) / abs(p)
        return None

    rev_g  = growth("revenue")
    pat_l  = latest("pat")
    pat_p  = prior("pat")
    eq_l   = latest("total_equity")
    ast_g  = growth("total_assets")

    # Revenue flags
    if rev_g is not None:
        if rev_g > 0.4:
            flags.append(("green", "✅", "Strong Revenue Growth",
                f"Revenue grew {rev_g*100:.1f}% period-on-period — well above average."))
        elif rev_g > 0.1:
            flags.append(("green", "✅", "Positive Revenue Growth",
                f"Revenue grew {rev_g*100:.1f}% period-on-period."))
        elif rev_g < -0.2:
            flags.append(("red", "🚩", "Revenue Declining Sharply",
                f"Revenue fell {abs(rev_g)*100:.1f}% period-on-period. Investigate demand trends."))
        elif rev_g < 0:
            flags.append(("warn", "⚠️", "Flat / Slightly Declining Revenue",
                f"Revenue change: {rev_g*100:.1f}%."))

    # Profitability flags
    if pat_l is not None:
        if pat_l > 0:
            if pat_p is not None and pat_p < 0:
                flags.append(("green", "✅", "Return to Profitability",
                    f"Profit turned positive ({_fmt(pat_l)}) from a prior loss — strong turnaround signal."))
            elif pat_p is not None and pat_p > 0 and pat_l > pat_p * 1.5:
                flags.append(("green", "✅", "Profit Growth Accelerating",
                    f"PAT of {_fmt(pat_l)} is more than 50% above prior period's {_fmt(pat_p)}."))
            else:
                flags.append(("green", "✅", "Profitable",
                    f"Latest PAT: {_fmt(pat_l)}. Company is generating positive returns."))
        else:
            if pat_p is not None and pat_p > 0:
                flags.append(("red", "🚩", "Profit Turned to Loss",
                    f"PAT is {_fmt(pat_l)} vs {_fmt(pat_p)} prior. Deterioration warrants scrutiny."))
            else:
                flags.append(("red", "🚩", "Loss-Making",
                    f"Latest PAT: {_fmt(pat_l)}. Company is loss-making. Review cost and revenue drivers."))

    # Equity flags
    if eq_l is not None:
        if eq_l < 0:
            flags.append(("red", "🚩", "Negative Equity",
                f"Total equity is {_fmt(eq_l)} — technically insolvent position."))
        else:
            flags.append(("green", "✅", "Positive Equity Base",
                f"Equity of {_fmt(eq_l)} provides a solid capital foundation."))

    # Asset growth
    if ast_g is not None:
        if ast_g > 0.3:
            flags.append(("green", "✅", "Strong Asset Growth",
                f"Total assets grew {ast_g*100:.1f}% period-on-period."))
        elif ast_g < -0.1:
            flags.append(("warn", "⚠️", "Shrinking Asset Base",
                f"Total assets declined {abs(ast_g)*100:.1f}%."))

    # Trend consistency
    pat_series = trend_data.get("pat", [])
    if len(pat_series) >= 3:
        recent = [v for _, v in pat_series[-3:] if v is not None]
        if len(recent) == 3:
            if all(recent[i] < recent[i+1] for i in range(2)):
                flags.append(("green", "✅", "Consistent Earnings Improvement",
                    "Profit has improved for 3 consecutive periods."))
            elif all(recent[i] > recent[i+1] for i in range(2)):
                flags.append(("red", "🚩", "Consecutive Earnings Decline",
                    "Profit has declined for 3 consecutive periods."))

    rev_series = trend_data.get("revenue", [])
    if len(rev_series) >= 3:
        recent_rev = [v for _, v in rev_series[-3:] if v is not None]
        if len(recent_rev) == 3 and all(recent_rev[i] < recent_rev[i+1] for i in range(2)):
            flags.append(("green", "✅", "Consistent Revenue Growth",
                "Revenue has grown for 3 consecutive periods."))

    # Scoring → signal
    score = 0
    if rev_g and rev_g > 0.15:   score += 2
    if rev_g and rev_g > 0.4:    score += 1
    if pat_l and pat_l > 0:      score += 2
    if pat_p and pat_l and pat_l > pat_p: score += 1
    if eq_l and eq_l > 0:        score += 1
    if eq_l and eq_l < 0:        score -= 3
    if pat_l and pat_l < 0:      score -= 2
    if rev_g and rev_g < -0.1:   score -= 2

    if score >= 5:   signal = "BUY"
    elif score >= 2: signal = "HOLD"
    elif score >= 0: signal = "WATCH"
    else:            signal = "AVOID"

    if not flags:
        flags.append(("warn", "⚠️", "Insufficient Data",
            "Not enough financial data parsed to generate detailed flags. "
            "Check that the source financial_lines.txt files contain recognised line formats."))

    return signal, flags


def _fmt(val):
    """Format a value as ₦XB / ₦XM / negative variant."""
    if val is None:
        return "N/A"
    neg = val < 0
    a = abs(val)
    if a >= 1_000_000_000_000:
        s = f"₦{a/1_000_000_000_000:.2f}T"
    elif a >= 1_000_000_000:
        s = f"₦{a/1_000_000_000:.2f}B"
    elif a >= 1_000_000:
        s = f"₦{a/1_000_000:.1f}M"
    elif a >= 1_000:
        s = f"₦{a/1_000:.0f}K"
    else:
        s = f"₦{a:,.0f}"
    return f"−{s}" if neg else s


# ─────────────────────────────────────────────────────────────────────────────
# RATIO COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def _compute_ratios(trend_data):
    ratios = {}

    def lv(key):
        s = trend_data.get(key, [])
        return s[-1][1] if s else None

    def pv(key):
        s = trend_data.get(key, [])
        return s[-2][1] if len(s) >= 2 else None

    rev = lv("revenue");  rev_p = pv("revenue")
    gp  = lv("gross_profit")
    op  = lv("operating_profit")
    pat = lv("pat")
    ast = lv("total_assets"); ast_p = pv("total_assets")
    eq  = lv("total_equity")

    if rev and rev_p and rev_p != 0:
        g = (rev - rev_p) / abs(rev_p) * 100
        ratios["Revenue Growth (Period-on-Period)"] = f"{'+' if g>=0 else ''}{g:.1f}%"
    if gp and rev and rev != 0:
        ratios["Gross Margin"] = f"{gp/rev*100:.1f}%"
    if op and rev and rev != 0:
        ratios["Operating Margin"] = f"{op/rev*100:.1f}%"
    if pat and rev and rev != 0:
        ratios["Net Margin"] = f"{pat/rev*100:.1f}%"
    if ast and ast_p and ast_p != 0:
        ag = (ast - ast_p) / abs(ast_p) * 100
        ratios["Asset Growth (Period-on-Period)"] = f"{'+' if ag>=0 else ''}{ag:.1f}%"
    if pat and eq and eq > 0:
        ratios["Return on Equity (est.)"] = f"{pat/eq*100:.1f}%"
    if pat and ast and ast != 0:
        ratios["Return on Assets (est.)"] = f"{pat/ast*100:.2f}%"
    if rev:
        ratios["Latest Revenue"] = _fmt(rev)
    if pat:
        ratios["Latest PAT"] = _fmt(pat)
    if ast:
        ratios["Latest Total Assets"] = _fmt(ast)
    if eq:
        ratios["Latest Total Equity"] = _fmt(eq)
    return ratios


# ─────────────────────────────────────────────────────────────────────────────
# FINANCIAL LINES FILTER
# ─────────────────────────────────────────────────────────────────────────────

_KEY_TERMS = [
    "revenue", "turnover", "gross earnings", "profit", "loss", "tax",
    "assets", "liabilities", "equity", "eps", "earnings per share",
    "gross profit", "operating profit", "income", "cash",
    "dividend", "finance income", "finance cost", "net interest", "interest income",
]
_HIGHLIGHT_TERMS = [
    "revenue", "turnover", "profit after tax", "profit for the year",
    "profit for the period", "loss after tax", "loss for the year",
    "loss for the period", "total assets", "total liabilities",
    "total equity", "earnings per share", "operating profit",
    "profit before tax", "loss before tax", "gross profit", "net interest income",
]


def _filter_key_lines(raw_lines, max_lines=150):
    result = []
    for line in raw_lines:
        line = line.strip()
        if not line or len(line) < 8:
            continue
        ll = line.lower()
        if any(t in ll for t in _KEY_TERMS):
            result.append({"line": line,
                           "highlighted": any(t in ll for t in _HIGHLIGHT_TERMS)})
        if len(result) >= max_lines:
            break
    return result


# ─────────────────────────────────────────────────────────────────────────────
# CSV HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _read_csv(fpath):
    rows = []
    try:
        with open(fpath, encoding="utf-8", errors="replace") as f:
            for row in csv.reader(f):
                rows.append([c.strip().replace("\r", " ").replace("\n", " ") for c in row])
    except Exception:
        pass
    return rows


def _is_meaningful_table(rows):
    if len(rows) < 2:
        return False
    return sum(1 for r in rows for c in r if c.strip()) >= 4


def _table_short_label(fname, stem):
    short = fname[len(stem):].lstrip("-_").replace(".csv", "")
    m = re.search(r'page(\d+)_table(\d+)', short)
    return f"Page {m.group(1)} · Table {m.group(2)}" if m else (
        short.replace("_", " ").strip().title() or fname)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def _get_index():
    """Scan processed dir once and cache forever (cleared on restart)."""
    return _scan_processed_dir()


def get_all_companies():
    """Sorted list of (ticker, display_label) for the dropdown."""
    return sorted(
        [(t, f"{t} — {d['name']}") for t, d in _get_index().items()],
        key=lambda x: x[1]
    )


def get_company_data(ticker):
    """
    Return the full context dict for a company detail page.
    Everything — KPIs, charts, ratios, flags, tables, fin-lines —
    is derived automatically from the processed files.
    Returns None if ticker unknown.
    """
    index = _get_index()
    ticker = ticker.upper()
    if ticker not in index:
        return None

    meta    = index[ticker]
    filings = meta["filings"]

    # ── Parse metrics from every filing ───────────────────────────────────
    trend_data = {}                 # {key: [(period_label, value), ...]}
    all_parsed = []                 # [(period_label, metrics_dict)]

    for filing in filings:
        lbl     = filing["period"]["period_label"]
        metrics = _parse_filing_metrics(filing["fin_lines_path"])
        all_parsed.append((lbl, metrics))
        for key, (cur, _) in metrics.items():
            if cur is not None:
                trend_data.setdefault(key, []).append((lbl, cur))

    # Deduplicate trend points with the same label
    for key in trend_data:
        seen, deduped = set(), []
        for lbl, val in trend_data[key]:
            if lbl not in seen:
                seen.add(lbl)
                deduped.append((lbl, val))
        trend_data[key] = deduped

    # ── KPIs from the most recent filing ──────────────────────────────────
    kpis = {}
    if all_parsed:
        latest_lbl, latest_m = all_parsed[-1]
        for key, label, _ in METRIC_PATTERNS:
            if key in latest_m:
                cur, prv = latest_m[key]
                val_str = _fmt(cur)
                if prv and prv != 0:
                    pct  = (cur - prv) / abs(prv) * 100
                    sign = "+" if pct >= 0 else ""
                    sub  = f"{sign}{pct:.1f}% vs prior period"
                else:
                    sub = f"Period: {latest_lbl}"
                kpis[label] = (val_str, sub)

    # ── Ratios, signal, flags ──────────────────────────────────────────────
    ratios         = _compute_ratios(trend_data)
    signal, flags  = _compute_signal_and_flags(trend_data)

    # ── CSV tables ─────────────────────────────────────────────────────────
    csv_tables = []
    for filing in filings:
        lbl = filing["period"]["period_label"]
        for cfname, cfpath in filing["csv_paths"]:
            rows = _read_csv(cfpath)
            if rows and _is_meaningful_table(rows):
                csv_tables.append({
                    "label":     f"{lbl} · {_table_short_label(cfname, filing['stem'])}",
                    "filename":  cfname,
                    "headers":   rows[0],
                    "rows":      rows[1:],
                    "row_count": len(rows) - 1,
                    "filing":    lbl,
                })

    # ── Financial lines ────────────────────────────────────────────────────
    financial_lines, seen_keys = [], set()
    for filing in filings:
        lbl = filing["period"]["period_label"]
        try:
            with open(filing["fin_lines_path"], encoding="utf-8", errors="replace") as f:
                raw = [l.rstrip() for l in f]
        except Exception:
            continue
        for item in _filter_key_lines(raw):
            dk = re.sub(r'\s+', ' ', item["line"].lower())[:65]
            if dk not in seen_keys:
                seen_keys.add(dk)
                item["filing"] = lbl
                financial_lines.append(item)

    # ── Segment chart — revenue by period (proxy) ─────────────────────────
    rev_s = trend_data.get("revenue", [])[-8:]
    PALETTE = ["#00e5a0","#3b82f6","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#f97316","#84cc16"]

    latest_period   = filings[-1]["period"]["period_label"] if filings else "Unknown"
    latest_month    = filings[-1]["period"].get("filing_month", "") if filings else ""

    return {
        "ticker":          ticker,
        "name":            meta["name"],
        "sector":          meta["sector"],
        "period":          latest_period,
        "filing_date":     latest_month,
        "signal":          signal,
        "kpis":            kpis,
        "ratios":          ratios,
        "flags":           flags,
        "total_tables":    len(csv_tables),
        "csv_tables":      csv_tables,
        "financial_lines": financial_lines,
        "filings_count":   len(filings),
        "revenue_chart": {
            "labels": [x[0] for x in trend_data.get("revenue", [])],
            "values": [x[1] for x in trend_data.get("revenue", [])],
        },
        "pat_chart": {
            "labels": [x[0] for x in trend_data.get("pat", [])],
            "values": [x[1] for x in trend_data.get("pat", [])],
        },
        "segment_chart": {
            "labels": [x[0] for x in rev_s],
            "values": [x[1] for x in rev_s],
            "colors": [PALETTE[i % len(PALETTE)] for i in range(len(rev_s))],
        },
    }