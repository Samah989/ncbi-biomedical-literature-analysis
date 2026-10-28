#!/bin/bash
# ---------------------------------------------------------------------------
# Pre-submit sanity check for the NCBI project. Run in osg/ dir on the OSG
# access point before condor_submit. Includes the NCBI-specific credential
# check that the other projects don't need.
#
#     source ~/.ncbi_env && cd ~/ncbi-analysis/osg && bash preflight.sh
# ---------------------------------------------------------------------------
set -u
cd "$(dirname "$0")"

problems=0
say_ok()   { echo "  [ok]    $1"; }
say_fail() { echo "  [FAIL]  $1"; problems=$((problems+1)); }
say_warn() { echo "  [warn]  $1"; }

echo "==> NCBI preflight in $(pwd)"

[ -d logs ] && say_ok "logs/ directory exists" || say_fail "logs/ directory missing         fix:  mkdir -p logs"

for w in pull_data.sh run_regression.sh; do
  if [ -f "$w" ]; then
    [ -x "$w" ] && say_ok "$w is executable" || say_fail "$w not executable        fix:  chmod +x $w"
  fi
done

[ -r requirements-osg.txt ]  && say_ok "requirements-osg.txt present"  || say_fail "requirements-osg.txt missing"
[ -r pull_all_pubmed.py ]    && say_ok "pull_all_pubmed.py present"    || say_fail "pull_all_pubmed.py missing"
[ -r run_regression.py ]     && say_ok "run_regression.py present"     || say_fail "run_regression.py missing"

if [ -d ../src ] && [ -f ../src/__init__.py ]; then
  say_ok "../src package present with __init__.py"
elif [ -d ../src ]; then
  say_fail "../src exists but has no __init__.py    fix:  touch ../src/__init__.py"
else
  say_fail "../src not found                          fix:  rsync the full project up"
fi

if [ -d ../data ]; then
  n=$(ls ../data/*.parquet 2>/dev/null | wc -l)
  [ "$n" -gt 0 ] && say_ok "../data has $n parquet file(s)" \
                 || say_warn "../data exists but is empty  -  pull_data must complete first"
else
  say_warn "../data does not exist yet  -  expected if you haven't run pull_data"
fi

# NCBI-specific: credentials must be in the submitter's env or environment= gets empty strings
if [ -n "${NCBI_API_KEY:-}" ]; then
  say_ok "NCBI_API_KEY is set (${#NCBI_API_KEY} chars)  -  will be passed via environment= directive"
else
  say_fail "NCBI_API_KEY is not set             fix:  source ~/.ncbi_env before condor_submit"
fi
if [ -n "${NCBI_EMAIL:-}" ]; then
  say_ok "NCBI_EMAIL is set (${NCBI_EMAIL})"
else
  say_warn "NCBI_EMAIL is not set  -  recommended by NCBI for polite-use identification"
fi
if [ -n "${FIELD_QUERY:-}" ]; then
  say_ok "FIELD_QUERY is set  -  pull_all_pubmed.py will use it"
else
  say_warn "FIELD_QUERY is not set  -  pull_all_pubmed.py will fall back to the CRISPR default"
fi

command -v condor_submit >/dev/null 2>&1 \
  && say_ok "condor_submit in PATH" \
  || say_fail "condor_submit not in PATH  -  are you on the access point?"

command -v condor_status >/dev/null 2>&1 && {
  avail=$(condor_status -avail 2>/dev/null | grep -c "^slot" || true)
  [ "${avail:-0}" -gt 100 ] && say_ok "condor_status reports ${avail} available slots" \
                            || say_warn "condor_status reports only ${avail:-0} slots"
}

for s in pull_data.submit run_regression.submit; do
  if [ -f "$s" ]; then
    if condor_submit -dry-run /tmp/preflight.$s.dry "$s" >/dev/null 2>&1; then
      say_ok "$s parses cleanly"
    else
      say_fail "$s failed dry-run parse                fix:  condor_submit -dry-run /tmp/dry $s"
    fi
    rm -f /tmp/preflight.$s.dry
  fi
done

echo
[ $problems -eq 0 ] && { echo "==> All checks passed. Safe to condor_submit."; exit 0; } \
                    || { echo "==> $problems problem(s) above. Fix and re-run preflight."; exit 1; }
