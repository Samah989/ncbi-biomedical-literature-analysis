# NCBI Biomedical Literature Analysis

Panel research on the biomedical literature using NCBI E-utilities
(PubMed, ClinicalTrials.gov linkage, MeSH). Three research questions,
one per notebook, all runnable locally on a modest slice and scalable
to the OSPool HTCondor cluster at `ap40.uw.osg-htc.org` for full-panel
runs with bootstrap SEs.

## Author

Samah Alshrief · [github.com/Samah989](https://github.com/Samah989)

## Research questions

1. **Country × year publication panel**  -  For a chosen biomedical field
   (default: CRISPR), which country characteristics predict publication
   output, and how has the geographic distribution shifted?
2. **Journal characteristics and impact**  -  Within the field, what
   journal-level attributes (age, open-access status, MeSH breadth)
   predict publication volume?
3. **Retractions in the biomedical literature**  -  Has the retraction
   rate risen over time, and which country-level factors predict
   higher within-country trends?

Each question is documented in a Jupyter notebook and mirrored by a
matching HTCondor submit file for OSPool.

## The tutorial notebook is deliberately expanded

`notebooks/00_ncbi_api_tutorial.ipynb` covers not just the API mechanics
but the full context  -  what NCBI is as an institution, the database
landscape, the Entrez query language (field tags, MeSH, ATM), all nine
E-utilities, rate-limit policy, the WebEnv history-server pattern, and
a biology glossary for anyone new to the vocabulary. If you're building
bibliometric intuition, read that notebook completely before touching
the RQ notebooks.

## Repository layout

```
ncbi-biomedical-literature-analysis/
├── notebooks/
│   ├── 00_ncbi_api_tutorial.ipynb           Expanded background + walk-through
│   ├── 01_rq1_country_publication_panel.ipynb
│   ├── 02_rq2_journal_impact.ipynb
│   └── 03_rq3_retractions.ipynb
├── src/
│   ├── ncbi_client.py    E-utilities client with WebEnv history + throttling
│   └── regression.py     Two-way FE panel helper (shared shape with sibling repos)
├── osg/
│   ├── README.md
│   ├── pull_data.submit / pull_data.sh / pull_all_pubmed.py
│   ├── run_regression.submit / run_regression.sh / run_regression.py
│   └── requirements-osg.txt
├── data/                 Parquet cache (gitignored)
├── results/              Regression tables + figures (gitignored)
├── setup_instructions.md First-run commands + NCBI API key setup
├── requirements.txt
└── .gitignore
```

## Getting started (local, 15 minutes)

```bash
cd "GitHub Tutorials/ncbi-biomedical-literature-analysis"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional but strongly recommended  -  takes 3 min at ncbi.nlm.nih.gov/account
export NCBI_API_KEY="paste-your-40-char-key"
export NCBI_EMAIL="you@example.com"

jupyter lab
```

Open `notebooks/00_ncbi_api_tutorial.ipynb` first. Then RQ notebooks in
any order.

## Scaling to OSPool

See [`osg/README.md`](osg/README.md) for the SSH + `rsync` + `condor_submit`
flow. The one gotcha vs the sibling repos: you must place your NCBI API
key in `~/.ncbi_env` on the access point (instructions in that README).

## Data source

- **NCBI E-utilities**  -  <https://www.ncbi.nlm.nih.gov/books/NBK25497/>
- **PubMed / MEDLINE**  -  the primary literature database
- **MeSH**  -  Medical Subject Headings vocabulary, browsable at <https://meshb.nlm.nih.gov/>

## License

Private research repository. Not for redistribution without author permission.
