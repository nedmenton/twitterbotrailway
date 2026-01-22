# Crypto Intelligence - Railway Deployment

Automated weekly discovery of early-stage crypto projects using the Sorsa API.

## Quick Deploy to Railway

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Name it `crypto-intelligence` (or whatever you want)
3. Keep it private
4. Click "Create repository"

### Step 2: Push This Code

In your terminal:

```bash
cd ~/crypto-intel  # or wherever you put these files
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/crypto-intelligence.git
git push -u origin main
```

### Step 3: Deploy on Railway

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your `crypto-intelligence` repo
5. Railway will auto-detect Python and deploy

### Step 4: Add Environment Variables

In Railway dashboard, go to your project → Variables → Add these:

| Variable | Value |
|----------|-------|
| `SORSA_API_KEY` | `ebd63ef7-b0bb-4bde-92e3-5ae87692c781` |
| `GOOGLE_SHEETS_ID` | Your Google Sheet ID (from the URL) |
| `GOOGLE_SHEETS_CREDS` | Your full Google service account JSON (paste the entire JSON) |

### Step 5: Set Up Weekly Cron (Optional)

For automatic weekly runs:

1. In Railway, go to your project settings
2. Add a Cron trigger: `0 18 * * 0` (runs every Sunday at 6 PM UTC)

Or run manually anytime by clicking "Deploy" in Railway.

## Environment Variables Explained

- **SORSA_API_KEY**: Your Sorsa (formerly TweetScout) API key
- **GOOGLE_SHEETS_ID**: The ID from your Google Sheet URL (e.g., from `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`)
- **GOOGLE_SHEETS_CREDS**: The full JSON content of your Google service account credentials

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SORSA_API_KEY="your-key"
export GOOGLE_SHEETS_ID="your-sheet-id"
export GOOGLE_SHEETS_CREDS='{"type":"service_account",...}'

# Run
python main.py
```

## What It Does

1. Checks 200+ crypto power users for new follows in the last 7 days
2. Scores each discovered account based on:
   - Follower count (fewer = better for early discovery)
   - Account age (newer = better)
   - Crypto keywords in bio
   - Discord/Telegram links
   - Which power users follow them
3. Saves high-scoring accounts (200+ points) to database
4. Uploads new discoveries to Google Sheets

## Files

- `main.py` - Main automation script
- `requirements.txt` - Python dependencies
- `railway.json` - Railway deployment config
- `crypto_intelligence.db` - SQLite database (created on first run)
