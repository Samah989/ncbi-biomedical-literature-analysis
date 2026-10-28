"""
Batch pull for OSPool. Runs the three RQ queries and writes parquet
files to ./data/.
"""
import sys
import logging
import os

sys.path.insert(0, ".")
from src.ncbi_client import pubmed_query_to_dataframe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

FIELD_QUERY = os.environ.get("FIELD_QUERY", '"CRISPR-Cas Systems"[mesh] OR "CRISPR"[tiab]')

# NCBI's WebEnv-based EFetch has a hard 10,000-record ceiling per session.
# Going past retstart=10000 returns HTTP 400. For pulls larger than that,
# split the query by year and issue one esearch per year. For this tutorial
# pipeline we cap at 10,000 records per query and take the most recent.
CAP = 10_000

# RQ1 & RQ2 share the field pull (2000-2023).
pubmed_query_to_dataframe(
    FIELD_QUERY,
    mindate="2000/01/01", maxdate="2023/12/31",
    max_records=CAP,
)

# RQ3  -  all retractions 2000-2023.
pubmed_query_to_dataframe(
    '"Retracted Publication"[pt]',
    mindate="2000/01/01", maxdate="2023/12/31",
    max_records=CAP,
)

print("Done.")
