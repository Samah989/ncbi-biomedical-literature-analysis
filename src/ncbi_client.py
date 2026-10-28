"""
NCBI E-utilities client for PubMed and other Entrez databases.

The E-utilities are NCBI's official programmatic interface. They speak HTTP
with query-string parameters and return either XML (default) or JSON. Nine
utilities cover the full workflow  -  this module wraps the four you need
for literature analysis: ESearch, ESummary, EFetch, EPost/history.

NCBI rate limits:
- No API key: 3 requests/second, no overall quota.
- With free API key: 10 requests/second. Sign up at
  https://www.ncbi.nlm.nih.gov/account/settings/  →  API Key Management.

Set your API key + email in the environment before importing:
    export NCBI_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    export NCBI_EMAIL="you@example.com"

Docs:
- Book: https://www.ncbi.nlm.nih.gov/books/NBK25497/
- Utilities in one place: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- Rate limit policy: https://support.nlm.nih.gov/kbArticle/?pn=KA-05316
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import pandas as pd
import requests

log = logging.getLogger(__name__)

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)

API_KEY = os.environ.get("NCBI_API_KEY", "")
EMAIL   = os.environ.get("NCBI_EMAIL", "")
TOOL    = "cowork-ncbi-panel-analysis"

# Rate: 10 req/s if we have a key, 3 req/s otherwise. Sleep = 1 / rate.
REQ_INTERVAL = 1 / 10 if API_KEY else 1 / 3
_last_call = 0.0


def _throttle():
    """Enforce NCBI rate limit locally so we don't get 429'd."""
    global _last_call
    dt = time.monotonic() - _last_call
    if dt < REQ_INTERVAL:
        time.sleep(REQ_INTERVAL - dt)
    _last_call = time.monotonic()


def _common_params():
    p = {"tool": TOOL}
    if API_KEY: p["api_key"] = API_KEY
    if EMAIL:   p["email"]   = EMAIL
    return p


def _get(path: str, params: dict, retries: int = 5, backoff: int = 2):
    for attempt in range(1, retries + 1):
        _throttle()
        try:
            r = requests.get(f"{BASE}/{path}", params={**_common_params(), **params}, timeout=60)
            r.raise_for_status()
            return r
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            if attempt == retries:
                raise
            sleep = backoff * (2 ** (attempt - 1))
            log.warning("NCBI error %s (attempt %d/%d); sleeping %ds", e, attempt, retries, sleep)
            time.sleep(sleep)


# ---------------------------------------------------------------------------
# ESearch: text query → list of PMIDs (or other UIDs), with optional history.
# ---------------------------------------------------------------------------

def esearch(
    query: str,
    db: str = "pubmed",
    retmax: int = 10000,
    mindate: str | None = None,
    maxdate: str | None = None,
    datetype: str = "pdat",
    use_history: bool = True,
) -> dict:
    """
    Run one ESearch. If the result set is larger than `retmax`, prefer
    `use_history=True` and then batch-fetch via EFetch/ESummary using the
    returned WebEnv + query_key.

    Returns a dict:
        {"count": int, "ids": [str], "webenv": str, "query_key": str}
    """
    params = {
        "db": db, "term": query, "retmax": retmax,
        "usehistory": "y" if use_history else "n",
        "retmode": "json",
        "datetype": datetype,
    }
    if mindate: params["mindate"] = mindate
    if maxdate: params["maxdate"] = maxdate

    r = _get("esearch.fcgi", params).json()
    result = r["esearchresult"]
    return {
        "count":     int(result.get("count", 0)),
        "ids":       result.get("idlist", []),
        "webenv":    result.get("webenv"),
        "query_key": result.get("querykey"),
    }


# ---------------------------------------------------------------------------
# EFetch: batch retrieve records for a set of PMIDs.
# ---------------------------------------------------------------------------

def efetch_pubmed_xml(
    pmids: Iterable[str] | None = None,
    webenv: str | None = None,
    query_key: str | None = None,
    count: int | None = None,
    batch_size: int = 200,
) -> ET.Element:
    """
    Fetch PubMed article records as XML. Provide either an explicit list of
    PMIDs OR a WebEnv/query_key pair from an ESearch history call.

    Returns an lxml-compatible ElementTree root of a synthetic
    <PubmedArticleSet> containing every batch's articles.
    """
    root = ET.Element("PubmedArticleSet")
    if pmids is not None:
        pmids = list(pmids)
        for start in range(0, len(pmids), batch_size):
            batch = pmids[start:start + batch_size]
            r = _get("efetch.fcgi", {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "rettype": "abstract",
            })
            for art in ET.fromstring(r.content):
                root.append(art)
    elif webenv and query_key and count is not None:
        for retstart in range(0, count, batch_size):
            r = _get("efetch.fcgi", {
                "db": "pubmed",
                "WebEnv": webenv, "query_key": query_key,
                "retstart": retstart, "retmax": batch_size,
                "retmode": "xml", "rettype": "abstract",
            })
            for art in ET.fromstring(r.content):
                root.append(art)
    else:
        raise ValueError("Provide either pmids OR (webenv, query_key, count).")
    return root


# ---------------------------------------------------------------------------
# XML → tidy DataFrame
# ---------------------------------------------------------------------------

def _text(node, path, default=None):
    el = node.find(path)
    return el.text if el is not None and el.text else default


def articles_to_dataframe(xml_root: ET.Element) -> pd.DataFrame:
    """
    Flatten a <PubmedArticleSet> XML tree to a tidy DataFrame.

    One row per article. First author's affiliation is used as the primary
    affiliation. Country is heuristically extracted from affiliation text.
    """
    rows = []
    for art in xml_root.findall(".//PubmedArticle"):
        med = art.find("MedlineCitation")
        pmid = _text(med, "PMID")
        article = med.find("Article") if med is not None else None
        if article is None:
            continue

        # Journal + year
        journal = article.find("Journal")
        journal_title = _text(journal, "Title") or _text(journal, "ISOAbbreviation")
        year = _text(article, "Journal/JournalIssue/PubDate/Year") \
            or _text(article, "Journal/JournalIssue/PubDate/MedlineDate", "")[:4]
        try:
            year_int = int(year) if year and year.isdigit() else None
        except ValueError:
            year_int = None

        title = _text(article, "ArticleTitle")

        # Authors + first-author affiliation
        authors = article.findall("AuthorList/Author") or []
        n_authors = len(authors)
        first_aff = ""
        if authors:
            first_aff = _text(authors[0], "AffiliationInfo/Affiliation", "") or ""

        # MeSH descriptors
        mesh = [_text(m, "DescriptorName") for m in med.findall("MeshHeadingList/MeshHeading")] if med is not None else []
        mesh = [m for m in mesh if m]

        # Publication types (used for retraction detection)
        pub_types = [pt.text for pt in article.findall("PublicationTypeList/PublicationType") if pt.text]

        rows.append({
            "pmid": pmid,
            "year": year_int,
            "journal": journal_title,
            "title": title,
            "n_authors": n_authors,
            "first_affiliation": first_aff,
            "mesh_terms": ";".join(mesh),
            "n_mesh": len(mesh),
            "pub_types": ";".join(pub_types),
            "is_retraction": "Retracted Publication" in pub_types,
            "is_retraction_notice": "Retraction of Publication" in pub_types,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["country"] = df["first_affiliation"].map(country_from_affiliation)
    return df


# ---------------------------------------------------------------------------
# Country extraction  -  MEDLINE affiliation strings are unstructured. This
# tries a couple of heuristics. Good enough for aggregate country stats;
# don't cite exact per-paper attributions without a manual audit.
# ---------------------------------------------------------------------------

# A short list of common country tokens. Extend as needed.
_COUNTRY_TOKENS = [
    "USA", "United States", "U.S.A.", "U.S.",
    "United Kingdom", "UK", "England", "Scotland", "Wales", "Northern Ireland",
    "China", "P.R. China", "PR China", "PRC",
    "Japan", "Germany", "France", "Italy", "Spain", "Canada", "Australia",
    "India", "Brazil", "Mexico", "Netherlands", "Sweden", "Switzerland",
    "Belgium", "Denmark", "Norway", "Finland", "Poland", "Russia",
    "South Korea", "Republic of Korea", "Korea",
    "Israel", "Turkey", "Iran", "Saudi Arabia", "UAE", "Egypt",
    "South Africa", "Nigeria", "Kenya",
    "Singapore", "Taiwan", "Hong Kong", "New Zealand", "Portugal",
    "Argentina", "Chile", "Colombia", "Ireland", "Austria", "Greece",
    "Czech Republic", "Hungary", "Romania",
]
_COUNTRY_NORMALIZE = {
    "U.S.": "USA", "U.S.A.": "USA", "United States": "USA",
    "UK": "United Kingdom", "England": "United Kingdom", "Scotland": "United Kingdom",
    "Wales": "United Kingdom", "Northern Ireland": "United Kingdom",
    "P.R. China": "China", "PR China": "China", "PRC": "China",
    "Republic of Korea": "South Korea", "Korea": "South Korea",
}


def country_from_affiliation(text: str) -> str | None:
    """Best-effort country tag from a MEDLINE affiliation string."""
    if not text:
        return None
    # Affiliations often end with "..., Country. Electronic address: ..."
    # Split on commas and check the last few tokens first.
    fragments = [t.strip(" .;") for t in text.replace("\n", " ").split(",")]
    for frag in reversed(fragments[-3:]):
        for token in _COUNTRY_TOKENS:
            if token.lower() == frag.lower():
                return _COUNTRY_NORMALIZE.get(token, token)
    # Fall back: substring anywhere.
    for token in _COUNTRY_TOKENS:
        if token in text:
            return _COUNTRY_NORMALIZE.get(token, token)
    return None


# ---------------------------------------------------------------------------
# High-level cached pipeline: query -> dataframe of articles.
# ---------------------------------------------------------------------------

def pubmed_query_to_dataframe(
    query: str,
    mindate: str | None = None,
    maxdate: str | None = None,
    max_records: int = 50000,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Full pipeline: ESearch (history) → EFetch (batched) → tidy DataFrame.
    Cached to parquet keyed by the (query, date range) tuple.
    """
    key = json.dumps({"q": query, "min": mindate, "max": maxdate, "n": max_records}, sort_keys=True)
    digest = hashlib.md5(key.encode()).hexdigest()[:10]
    cache = DATA_DIR / f"pubmed__{digest}.parquet"
    if use_cache and cache.exists():
        log.info("Cache hit: %s", cache.name)
        return pd.read_parquet(cache)

    # NCBI's EFetch caps WebEnv-based paging at retstart<10_000; anything
    # beyond returns HTTP 400. Cap here so callers can't accidentally overshoot.
    WEBENV_CAP = 10_000
    search = esearch(query, mindate=mindate, maxdate=maxdate, retmax=0, use_history=True)
    n_to_fetch = min(search["count"], max_records, WEBENV_CAP)
    if search["count"] > WEBENV_CAP:
        log.warning("Query returned %d hits; capping at %d due to NCBI WebEnv ceiling",
                    search["count"], WEBENV_CAP)
    log.info("ESearch found %d hits; fetching %d", search["count"], n_to_fetch)
    xml = efetch_pubmed_xml(webenv=search["webenv"], query_key=search["query_key"], count=n_to_fetch)
    df = articles_to_dataframe(xml)
    df.to_parquet(cache, index=False)
    log.info("Cached %d rows → %s", len(df), cache.name)
    return df
