# Remaining work (needs a person, not code)

Last checked 2026-10-07. Code is complete; 39 tests pass. App runs, the dashboard renders and the offline advisor answers.

## 1. Electronics data: DONE (2026-10-07)
`events.csv` is in `data/raw/electronics/`. All 39 tests pass (none skipped) and the reference numbers reproduce: 885,129 rows, 655 duplicates and 162 null-session rows removed, 407,237 customers, 490,633 sessions, 1,042,339 of 1,216,213 transitions used, AOV 210.49, live vs frozen revenue per 1k visitors 13,332 vs 10,779, drift in Nov {Product View, Purchase} and Jan {Product View, Add to Cart}, held-out Jan log-loss 0.7467 / 0.7498 / 1.0685.

## 2. Cosmetics: DONE (2026-10-07)
Five monthly CSVs are in `data/raw/cosmetics/`. Results and caveats are in `REPORT_DRAFT.md` §6.2 and CLAUDE.md §4. Optional follow-ups: repeat on a different 10% sample (e.g. `user_id % 10 == 1`), and test the left-censoring explanation by restricting to customers whose first event is in October.

## 3. Finish the report
`docs/REPORT_DRAFT.md`: add team names and the extra references, read §6.2 and decide how much of its caveats to keep, and keep the Kaggle/REES46 attribution.

## 4. Fix the slides (the deck is not in this folder)
- Slide 6: "never" → "not found in the reviewed literature"
- Slides 9–10: "steady-state" → "absorption analysis"
- Slide 9: "Real dataset" box → "REES46 Electronics (Kaggle)"
- Recommendation box → "AI advisor (Claude + offline analyst)"

## 5. Teammate prep
Everyone reads `docs/FORMULAS_EXPLAINED.md`, including the viva questions at the end. Rehearse the 4-minute demo script in README §2.

## 6. Optional
Set `ANTHROPIC_API_KEY` in your environment (never in a file that gets committed) to see the Claude-backed advisor instead of the offline analyst.
