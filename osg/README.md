# Running on OSPool (ap40.uw.osg-htc.org)

Same pattern as the IPEDS and World Bank projects, with one extra step:
we need to make the NCBI API key available to the job.

## One-time setup on the access point

```bash
ssh samah.alshrief@ap40.uw.osg-htc.org

# Store your NCBI credentials once, outside the repo.
cat > ~/.ncbi_env <<'ENV'
export NCBI_API_KEY=<YOUR_NCBI_API_KEY>
export NCBI_EMAIL=<YOUR_EMAIL>
export FIELD_QUERY='"CRISPR-Cas Systems"[mesh] OR "CRISPR"[tiab]'
ENV
chmod 600 ~/.ncbi_env
mkdir -p ~/ncbi-analysis
exit
```

## Every run

```bash
cd ncbi-biomedical-literature-analysis

rsync -avz --delete \
  --exclude '.venv' --exclude '__pycache__' \
  --exclude 'data/*.parquet' --exclude 'results/*' \
  ./ samah.alshrief@ap40.uw.osg-htc.org:~/ncbi-analysis/

ssh samah.alshrief@ap40.uw.osg-htc.org
cd ~/ncbi-analysis/osg
mkdir -p logs
source ~/.ncbi_env       # so condor_submit sees the env vars
condor_submit pull_data.submit
condor_watch_q

condor_submit run_regression.submit
condor_watch_q
exit
```

Pull results back:

```bash
rsync -avz samah.alshrief@ap40.uw.osg-htc.org:~/ncbi-analysis/osg/results/ ./results/
rsync -avz samah.alshrief@ap40.uw.osg-htc.org:~/ncbi-analysis/osg/data/    ./data/
```

## Notes specific to NCBI

- NCBI limits are **10 req/s with a key, 3 req/s without.** Our client
  throttles locally. Multiple concurrent OSG jobs hitting NCBI from the
  same key will still be rate-limited **in aggregate**, so we intentionally
  queue only one `pull_data` job at a time. The `run_regression` jobs
  don't hit NCBI at all  -  they read the cached parquets.
- Very large pulls (>500K records) benefit from splitting by year and
  parallelizing. Ask for that when you want it  -  it's a small change
  to `pull_all_pubmed.py`.
