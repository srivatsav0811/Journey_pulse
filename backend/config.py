"""
config.py
=========
Every tunable constant in one place. The report's sensitivity checks change
these values and nothing else.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FRONTEND_DIR = ROOT / "frontend"

# --- State mapping (real clickstream data) ---------------------------------
CHURN_DAYS = 30          # no activity for this many days  ->  Exit (churn)
LOYAL_AT = 3             # this order number and above     ->  Loyal Customer
MIN_BATCH_DAYS = 14      # a first/last month with less coverage is merged into its neighbour

# --- Drift detection ---------------------------------------------------------
DRIFT_ALPHA = 0.05       # family-wise significance level (Holm-corrected across rows)
MIN_DRIFT_TV = 0.02      # a row must also move by at least this total-variation distance
MIN_OBSERVATIONS = 30    # rows with fewer transitions in either batch are not tested

# --- Adaptive updating -------------------------------------------------------
DEFAULT_STRATEGY = "adaptive_ewma"
BASE_ALPHA = 0.30        # weight on the new batch for rows with no meaningful drift
MAX_ALPHA = 0.80         # upper bound for strongly drifted rows
ALPHA_TV_SCALE = 0.05    # alpha = base + (max-base) * tanh(TV / scale); TV 0.05 -> alpha ~0.68
BAYES_DECAY = 0.90
WINDOW = 3

# --- What-if / optimisation --------------------------------------------------
DEFAULT_BUDGET = 0.05    # total probability (5 percentage points) the business can "buy"
DEFAULT_PER_LEVER_MAX = 0.03
GRID_STEP = 0.01         # brute-force verification step for the optimiser

# --- AI advisor --------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Which hosted model answers: "claude" or "groq". Default: Claude if its key is set, else Groq.
ADVISOR_PROVIDER = os.environ.get("ADVISOR_PROVIDER", "").lower()
ADVISOR_TIMEOUT_SECONDS = 25
ADVISOR_MAX_TOOL_ROUNDS = 5

# --- Server ------------------------------------------------------------------
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))


def advisor_provider() -> str:
    """"claude", "groq", or "offline" (no key set). Read at call time so tests can patch the keys."""
    if ADVISOR_PROVIDER == "groq" and GROQ_API_KEY:
        return "groq"
    if ADVISOR_PROVIDER == "claude" and ANTHROPIC_API_KEY:
        return "claude"
    if ANTHROPIC_API_KEY:
        return "claude"
    if GROQ_API_KEY:
        return "groq"
    return "offline"


def advisor_model(provider: str):
    return {"claude": ANTHROPIC_MODEL, "groq": GROQ_MODEL}.get(provider)
