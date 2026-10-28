# First-run instructions

All 20 project files are built. These are the commands **you** run in
your terminal  -  macOS blocks agents from typing into Terminal for safety.

## 1. Move to the project folder

```bash
cd ncbi-biomedical-literature-analysis
ls
```

## 2. Get an NCBI API key (3 minutes, strongly recommended)

Without a key you get 3 requests/second. With a key, 10 req/s. Same key
tied to your NCBI account works forever.

1. Sign in / create an account at <https://www.ncbi.nlm.nih.gov/account/>.
2. Account Settings → API Key Management → **Create an API Key**.
3. Copy the 40-character hex string.

Add these to your shell profile (`~/.zshrc` on modern Macs). Never commit
them:

```bash
echo 'export NCBI_API_KEY="paste-your-key-here"' >> ~/.zshrc
echo 'export NCBI_EMAIL="you@example.com"'       >> ~/.zshrc
source ~/.zshrc
```

## 3. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Push to the (already-created) private GitHub repo

```bash
git init
git branch -M main
git add .
git commit -m "Initial commit: NCBI biomedical literature panel analysis"
git remote add origin https://github.com/Samah989/ncbi-biomedical-literature-analysis.git
git push -u origin main
```

## 5. Launch JupyterLab and start with the tutorial

```bash
jupyter lab
```

Open `notebooks/00_ncbi_api_tutorial.ipynb`. That notebook is intentionally
deep  -  read it top to bottom before touching the RQ notebooks. Then run
`01`, `02`, `03` in any order.

## 6. Move to OSPool for the heavy runs

See [`osg/README.md`](osg/README.md).
