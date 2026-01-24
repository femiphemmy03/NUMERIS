# Week 1 Progress - First DB Insert

**Database**: Local PostgreSQL (`Numeris_db`)

**Table**: `financials`

**Schema summary**:
- id: serial PRIMARY KEY
- ticker: varchar(20) NOT NULL
- report_year: integer NOT NULL
- report_period: varchar(10)
- revenue: numeric(20,2)
- profit_after_tax: numeric(20,2)
- ... (full schema in docs/schema.md)

**Sample data (first row from Cadbury Q3 2025 PDF)**:

| ticker   | report_year | report_period | revenue       | profit_after_tax | shareholder_equity | source_url                                                                 |
|----------|-------------|---------------|---------------|------------------|--------------------|----------------------------------------------------------------------------|
| CADBURY  | 2025        | Q3            | 119245105000  | 9678649000       | 14057842000        | https://doclib.ngxgroup.com/.../cadbury_q3_2025.pdf                        |

Notes: Numbers in full NGN (PDF uses '000). Manual insert for Week 1 proof-of-concept.