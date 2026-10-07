# Remaining work (needs a person, not code)

Last checked 2026-10-07. Code is complete; 38 tests pass, 1 skipped (needs the real data). App runs, the dashboard renders and the offline advisor answers.

## 1. Get the Electronics data and verify the reference numbers
1. Download "eCommerce events history in electronics store" from Kaggle (mkechinov). Requires a Kaggle login.
2. Put the CSVs in `data/raw/electronics/`.
3. Run `python tests/run_tests.py`; the skipped test should now run.
4. Start the app, pick the Electronics dataset, and check against CLAUDE.md §4:
   - 885,129 rows; 655 duplicates and 162 null-session rows removed; 407,237 customers; 490,633 sessions
   - 1,042,339 transitions used of 1,216,213; batches Oct 2020, Nov 2020, Dec 2020, Jan 2021; AOV about 210.5
   - Live v3 vs frozen v0 revenue per 1k visitors 13,332 vs 10,779
   - Held-out Jan accuracy 66.5% vs baseline 58.1%; log-loss 0.7467 / 0.7498 / 1.0685
5. If anything differs, find out why before editing the report (CLAUDE.md §4).

## 2. Run Cosmetics once
Download the Cosmetics dataset, put the CSVs in `data/raw/cosmetics/` (it uses a 10% customer sample), run it, and fill in §6.2 of `REPORT_DRAFT.md`. This code path has never been run on real data.

## 3. Finish the report
`docs/REPORT_DRAFT.md`: add team names, the extra references, the Cosmetics section, and remove every **[verify]** tag once confirmed. Keep the Kaggle/REES46 attribution.

## 4. Fix the slides (the deck is not in this folder)
- Slide 6: "never" → "not found in the reviewed literature"
- Slides 9–10: "steady-state" → "absorption analysis"
- Slide 9: "Real dataset" box → "REES46 Electronics (Kaggle)"
- Recommendation box → "AI advisor (Claude + offline analyst)"

## 5. Teammate prep
Everyone reads `docs/FORMULAS_EXPLAINED.md`, including the viva questions at the end. Rehearse the 4-minute demo script in README §2.

## 6. Optional
Set `ANTHROPIC_API_KEY` in your environment (never in a file that gets committed) to see the Claude-backed advisor instead of the offline analyst.
