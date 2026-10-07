# Remaining work (needs a person, not code)

Last checked 2026-10-07. Code is complete; 39 tests pass. App runs, the dashboard renders and the offline advisor answers.

## 1. Electronics data: DONE (2026-10-07)
`events.csv` is in `data/raw/electronics/`. All 39 tests pass (none skipped) and the reference numbers reproduce: 885,129 rows, 655 duplicates and 162 null-session rows removed, 407,237 customers, 490,633 sessions, 1,042,339 of 1,216,213 transitions used, AOV 210.49, live vs frozen revenue per 1k visitors 13,332 vs 10,779, drift in Nov {Product View, Purchase} and Jan {Product View, Add to Cart}, held-out Jan log-loss 0.7467 / 0.7498 / 1.0685.

## 2. Run Cosmetics once
Download "eCommerce events history in cosmetics shop" from Kaggle (the `kz.csv` file you downloaded is a different dataset and cannot be used), put the CSVs in `data/raw/cosmetics/` (it uses a 10% customer sample), run it, and fill in §6.2 of `REPORT_DRAFT.md`. This code path has never been run on real data.

## 3. Finish the report
`docs/REPORT_DRAFT.md`: add team names, the extra references, the Cosmetics section, and Keep the Kaggle/REES46 attribution.

## 4. Fix the slides (the deck is not in this folder)
- Slide 6: "never" → "not found in the reviewed literature"
- Slides 9–10: "steady-state" → "absorption analysis"
- Slide 9: "Real dataset" box → "REES46 Electronics (Kaggle)"
- Recommendation box → "AI advisor (Claude + offline analyst)"

## 5. Teammate prep
Everyone reads `docs/FORMULAS_EXPLAINED.md`, including the viva questions at the end. Rehearse the 4-minute demo script in README §2.

## 6. Optional
Set `ANTHROPIC_API_KEY` in your environment (never in a file that gets committed) to see the Claude-backed advisor instead of the offline analyst.
