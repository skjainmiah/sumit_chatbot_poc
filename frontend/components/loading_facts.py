"""Loading animation that shows interesting American Airlines facts while waiting for responses."""
import random
import time
import threading
from pathlib import Path
import streamlit as st

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except ImportError:
    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import (
            add_script_run_ctx,
            get_script_run_ctx,
        )
    except ImportError:
        add_script_run_ctx = None
        get_script_run_ctx = None


# Load facts from external file with hardcoded fallback
_FACTS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "loading_facts.txt"

_FALLBACK_FACTS = [
    "American Airlines was founded in 1930 through the merger of over 80 small airlines.",
    "AA operates about 6,700 flights per day to nearly 350 destinations in 50+ countries.",
    "The AA fleet has over 900 mainline aircraft, making it one of the largest in the world.",
    "Dallas/Fort Worth International Airport (DFW) is American Airlines' largest hub.",
    "AA was the first airline to use an electronic booking system (SABRE) in the 1960s.",
]

def _load_facts() -> list:
    try:
        text = _FACTS_FILE.read_text(encoding="utf-8")
        facts = [line.strip() for line in text.splitlines() if line.strip()]
        if facts:
            return facts
    except Exception:
        pass
    return list(_FALLBACK_FACTS)

AA_FACTS = _load_facts()


def _pick_facts(count: int = 10) -> list:
    """Pick facts avoiding repeats within the current session."""
    shown = st.session_state.get("shown_facts_set", set())

    available = [f for f in AA_FACTS if f not in shown]
    if len(available) < count:
        # Reset when we've shown everything
        shown = set()
        available = list(AA_FACTS)

    selected = random.sample(available, min(count, len(available)))
    shown.update(selected)
    st.session_state["shown_facts_set"] = shown
    return selected


# Delay before facts appear (seconds). If the answer arrives before this,
# no facts are shown at all.
_INITIAL_DELAY = 2.0

# Minimum number of facts to display once the animation starts.
# The caller should wait for `min_shown_event` before clearing the placeholder.
_MIN_FACTS = 2


def show_loading_with_facts(placeholder):
    """Display animated AA facts in the given placeholder while a background task runs.

    The animation waits for an initial delay before showing anything. If the
    response arrives within that delay, no facts are displayed at all.

    Once facts start showing, at least ``_MIN_FACTS`` full facts are displayed
    before the ``min_shown_event`` fires.

    Args:
        placeholder: A streamlit st.empty() placeholder to render facts into.

    Returns:
        (stop_event, min_shown_event) – call ``stop_event.set()`` when the
        backend response is ready, then wait on ``min_shown_event`` before
        clearing the placeholder so the user sees at least 2 facts.
    """
    stop_event = threading.Event()
    min_shown_event = threading.Event()
    facts = _pick_facts(10)

    # Capture Streamlit script-run context so the thread can write to the placeholder
    ctx = get_script_run_ctx() if get_script_run_ctx else None

    def _animate():
        # --- Initial delay: wait before showing any facts ---
        # If stop_event fires during the delay the answer was fast → skip facts.
        if stop_event.wait(timeout=_INITIAL_DELAY):
            # Answer arrived during the delay — no facts needed
            min_shown_event.set()
            return

        idx = 0
        dot_cycle = 0
        facts_completed = 0  # counts full fact rotations

        while not stop_event.is_set():
            try:
                fact = facts[idx % len(facts)]
                dots = "." * (dot_cycle % 4)
                footer = f"Processing your query{dots}"
                placeholder.markdown(
                    f"""
                    <div style="
                        padding: 16px 20px;
                        background: linear-gradient(135deg, #0078d2 0%, #003366 100%);
                        border-radius: 10px;
                        color: white;
                        font-size: 15px;
                        line-height: 1.5;
                        margin: 8px 0;
                        animation: slideIn 0.5s ease-out;
                    ">
                        <div style="font-size: 12px; opacity: 0.8; margin-bottom: 6px;">
                            ✈️ Did you know?
                        </div>
                        <div>{fact}</div>
                        <div style="margin-top: 8px; font-size: 12px; opacity: 0.6;">
                            {footer}
                        </div>
                    </div>
                    <style>
                        @keyframes slideIn {{
                            from {{ opacity: 0; transform: translateY(-10px); }}
                            to {{ opacity: 1; transform: translateY(0); }}
                        }}
                    </style>
                    """,
                    unsafe_allow_html=True
                )
            except Exception:
                # Context lost (e.g. user navigated away) — stop gracefully
                break

            dot_cycle += 1
            if dot_cycle % 4 == 0:
                idx += 1
                facts_completed += 1
                if facts_completed >= _MIN_FACTS:
                    min_shown_event.set()

            # Wait ~0.75s per dot frame so a full fact cycle is ~3s
            stop_event.wait(timeout=0.75)

        # If we never reached _MIN_FACTS (e.g. only 1 shown), still unblock
        min_shown_event.set()

    thread = threading.Thread(target=_animate, daemon=True)
    if add_script_run_ctx and ctx:
        add_script_run_ctx(thread, ctx)
    thread.start()
    return stop_event, min_shown_event
