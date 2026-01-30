"""Loading animation that shows interesting American Airlines facts while waiting for responses."""
import random
import time
import threading
import streamlit as st


AA_FACTS = [
    "American Airlines was founded in 1930 through the merger of over 80 small airlines.",
    "AA operates about 6,700 flights per day to nearly 350 destinations in 50+ countries.",
    "The AA fleet has over 900 mainline aircraft, making it one of the largest in the world.",
    "American Airlines was the first airline to introduce a frequent flyer program, AAdvantage, in 1981.",
    "Dallas/Fort Worth International Airport (DFW) is American Airlines' largest hub.",
    "AA was the first airline to use an electronic booking system (SABRE) in the 1960s.",
    "American Airlines' fleet includes Boeing 737s, 777s, 787 Dreamliners, and Airbus A320 family aircraft.",
    "The AA eagle logo has been a symbol of the airline since the 1930s.",
    "American Airlines carried over 200 million passengers in a record year.",
    "AA employs over 130,000 people, including about 15,000 pilots and 27,000 flight attendants.",
    "American Airlines was the first US airline to introduce the Super 80 (MD-80) aircraft.",
    "The AA Admirals Club, started in 1939, was the first airline lounge in the world.",
    "American Airlines' network spans hubs at DFW, Charlotte, Chicago O'Hare, Miami, Philadelphia, Phoenix, and more.",
    "AA was a founding member of the oneworld alliance in 1999.",
    "American Airlines' Flagship First class debuted on the A321T transcon routes.",
    "The airline's maintenance base in Tulsa, Oklahoma is one of the largest in the world.",
    "AA's CR Smith Museum in Fort Worth preserves the history of American Airlines since 1930.",
    "American Airlines was the launch customer for the Boeing 707 in commercial service.",
    "The AA credit union has been serving employees and their families since 1935.",
    "American Airlines was the first to offer in-flight entertainment on domestic flights.",
    "AA pilots log millions of flight hours each year across the network.",
    "The American Airlines Training and Conference Center in Fort Worth spans over 40 acres.",
    "AA's cargo division handles millions of pounds of freight and mail every day.",
    "American Airlines merged with US Airways in 2013, creating the world's largest airline at the time.",
]


def show_loading_with_facts(placeholder):
    """Display animated AA facts in the given placeholder while a background task runs.

    Args:
        placeholder: A streamlit st.empty() placeholder to render facts into.

    Returns:
        A stop event (threading.Event) - call .set() on it when the task is done.
    """
    stop_event = threading.Event()

    def _animate():
        facts = random.sample(AA_FACTS, min(len(AA_FACTS), 10))
        idx = 0
        while not stop_event.is_set():
            fact = facts[idx % len(facts)]
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
                        Processing your query...
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
            idx += 1
            # Wait 3 seconds or until stop is signaled
            stop_event.wait(timeout=3.0)

    thread = threading.Thread(target=_animate, daemon=True)
    thread.start()
    return stop_event
