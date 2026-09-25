# The Push — Dolphins playoff dashboard

A GitHub Pages site that tracks the Miami Dolphins' playoff chase. The NFL does not use a single wild-card table, so the board is built around the things that actually decide January:

- **Two routes in** — win the AFC East, or take one of three AFC wild cards
- **The cut line** — seven AFC teams: four division winners and three wild cards
- **Football KPIs** — point differential, points and yards per game, third down, red-zone touchdowns, sack margin, turnover margin, time of possession
- **Tiebreakers** — head-to-head, division record, then conference record
- **The schedule** — games left, the bye, and a simulated playoff probability

## Enable it on GitHub

1. Create a public GitHub repo and push this project (default branch `main`).
2. In the repo: **Settings → Pages → Build and deployment**
   - Source: **Deploy from a branch**
   - Branch: `main`, folder: `/ (root)`
3. In **Settings → Actions → General**, allow GitHub Actions and permit the workflow to read and write contents so it can commit `data.json`.
4. Open **Actions → Update playoff dashboard → Run workflow** once so the first refresh is confirmed.

The public URL will be:

`https://<your-github-username>.github.io/dolphins-playoff-push/`

## What updates

A scheduled GitHub Action runs `scripts/fetch_playoff_data.py`, which writes `data.json` from ESPN's public NFL feeds. If nothing in the race changed, the workflow skips the commit.

## Local refresh

```bash
python3 scripts/fetch_playoff_data.py
python3 -m http.server 8080
```

Visit [http://localhost:8080](http://localhost:8080). Opening `index.html` as a file will block `fetch`.

## Notes

This is a fan dashboard, not an official NFL or Dolphins product. The playoff percentage is a season simulation from point differential and home field. It is not a betting line.
