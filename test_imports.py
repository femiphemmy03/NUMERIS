# test_imports.py - Quick check that all critical libraries import correctly

import pandas as pd
import numpy as np
import sqlalchemy
import pdfplumber
import tabula
import camelot
import requests
from dotenv import load_dotenv
import os

print("All key imports successful!")
print(f"Pandas version: {pd.__version__}")
print(f"SQLAlchemy version: {sqlalchemy.__version__}")
print(f"Current working directory: {os.getcwd()}")
print("Environment looks good — ready for DB connection tests next.")
