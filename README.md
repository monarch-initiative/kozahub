# KozaHub Dashboard

A static dashboard that monitors the health of all KozaHub ingest repositories in the `monarch-initiative` organization.

## Overview

The dashboard automatically discovers ingests via the `kozahub-ingest` GitHub topic and displays:
- Latest release information
- Last workflow run status
- Health status (healthy/stale/failed)

## Health Status Logic

- 🟢 **Healthy:** Latest release workflow succeeded AND release is <45 days old
- 🟡 **Stale:** Latest release workflow succeeded BUT release is >45 days old
- 🔴 **Failed:** Latest release workflow failed (or no release/workflow exists)

## Local Development

### Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager
- Python 3.11+
- GitHub personal access token (optional, for higher API rate limits)

### Setup

```bash
# Clone the repository
git clone https://github.com/monarch-initiative/kozahub-dashboard.git
cd kozahub-dashboard

# Install dependencies
uv sync
```

### Generate Dashboard Data

```bash
# Without authentication (60 requests/hour)
uv run scripts/fetch_dashboard_data.py

# With authentication (5000 requests/hour)
export GITHUB_TOKEN=your_token_here
uv run scripts/fetch_dashboard_data.py
```

### View Dashboard Locally

```bash
# Option 1: Open directly in browser
open index.html

# Option 2: Use a local server (recommended)
python3 -m http.server 8000
# Then visit http://localhost:8000
```

## Deployment

The dashboard is automatically deployed to GitHub Pages and updates every 6 hours via GitHub Actions.

**Live Dashboard:** https://monarch-initiative.github.io/kozahub-dashboard/

## Adding New Ingests

To add a new ingest to the dashboard:

1. Add the `kozahub-ingest` topic to your repository:
   - Go to your repo → About (gear icon) → Topics
   - Add `kozahub-ingest`
2. The dashboard will automatically discover it on the next update (within 6 hours)
3. Or manually trigger the "Update Dashboard Data" workflow for immediate updates

## File Structure

```
kozahub-dashboard/
├── pyproject.toml              # uv dependencies
├── scripts/
│   └── fetch_dashboard_data.py # Data collection script
├── index.html                  # Main dashboard page
├── styles.css                  # Dark mode styling
├── script.js                   # Load and render data
├── data/
│   └── dashboard-data.json     # Generated data (auto-updated)
└── .github/
    └── workflows/
        └── update-dashboard.yaml # Automation workflow
```

## Architecture

### Data Collection (Python)

- Queries GitHub API for repos with `kozahub-ingest` topic
- Fetches latest release and workflow run data
- Generates `data/dashboard-data.json`
- Runs via GitHub Actions every 6 hours

### Static Dashboard (HTML/CSS/JS)

- Loads JSON data client-side
- Renders status cards with UniFi-inspired dark mode design
- No build step required
- Deployed via GitHub Pages

## License

BSD 3-Clause License
