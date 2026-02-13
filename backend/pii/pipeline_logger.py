"""Dedicated PII pipeline trace logger.

Writes a clean, human-readable trace of every request to logs/pii_pipeline.log
showing exactly what data the LLM sees (with and without masking).
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set


_logger = logging.getLogger("pii_pipeline")


def setup_pii_pipeline_logger():
    """Configure the pii_pipeline logger to write to logs/pii_pipeline.log."""
    if _logger.handlers:
        return  # already set up

    log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    handler = logging.FileHandler(log_dir / "pii_pipeline.log", encoding="utf-8")
    handler.setLevel(logging.INFO)
    # Raw message only — the trace block already contains timestamps
    handler.setFormatter(logging.Formatter("%(message)s"))

    _logger.setLevel(logging.INFO)
    _logger.addHandler(handler)
    _logger.propagate = False  # don't echo to root / app.log


def _format_rows(rows: Optional[List[Dict[str, Any]]], max_rows: int = 5) -> str:
    """Format sample rows as col=val | col=val lines."""
    if not rows:
        return "  (no rows)"
    lines = []
    for row in rows[:max_rows]:
        parts = [f"{k}={v}" for k, v in row.items()]
        lines.append("  " + " | ".join(parts))
    if len(rows) > max_rows:
        lines.append(f"  ... ({len(rows)} rows total)")
    return "\n".join(lines)


def log_pii_trace(
    *,
    conv_id: str,
    pii_settings: Dict[str, Any],
    column_mask_settings: Optional[List[Dict[str, Any]]],
    user_prompt: str,
    masked_prompt: str,
    pii_map: Dict[str, str],
    sql: Optional[str],
    results: Optional[Dict[str, Any]],
    masked_results: Optional[Dict[str, Any]],
    summary: Optional[str],
):
    """Write a full pipeline trace block to pii_pipeline.log."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "=" * 80

    lines: List[str] = [
        "",
        sep,
        f"PII PIPELINE TRACE | {now} | conv={conv_id}",
        sep,
    ]

    # --- SETTINGS ---
    pii_enabled = pii_settings.get("enabled", False)
    lines.append("")
    lines.append("--- SETTINGS ---")
    lines.append(f"Input PII Masking: {'ON' if pii_enabled else 'OFF'}")

    # Column-level masking summary
    if column_mask_settings:
        enabled_masks: Dict[str, List[str]] = {}
        for m in column_mask_settings:
            if m.get("enabled"):
                key = f"{m['db_name']}.{m['table_name']}"
                enabled_masks.setdefault(key, []).append(m["column_name"])
        if enabled_masks:
            lines.append("Column-Level Masking: ON")
            for table, cols in enabled_masks.items():
                lines.append(f"  Masked columns: {table} -> {', '.join(cols)}")
        else:
            lines.append("Column-Level Masking: OFF (no columns enabled)")
    else:
        lines.append("Column-Level Masking: OFF")

    # --- STEP 1: USER PROMPT ---
    lines.append("")
    lines.append("--- STEP 1: USER PROMPT ---")
    lines.append(f'Original: "{user_prompt}"')
    if pii_map:
        lines.append(f'After Input Masking: "{masked_prompt}"')
        lines.append(f"  PII tokens: {len(pii_map)}")
        for token, original in pii_map.items():
            lines.append(f"    {token} <- \"{original}\"")
    else:
        lines.append(f'After Input Masking: "{masked_prompt}" (no changes)')

    # --- STEP 2: LLM GENERATED SQL ---
    lines.append("")
    lines.append("--- STEP 2: LLM GENERATED SQL ---")
    lines.append(sql if sql else "(no SQL generated)")

    # --- STEP 3: SQL RESULTS (real data) ---
    lines.append("")
    real_rows = results.get("rows") if results else None
    row_count = results.get("row_count", 0) if results else 0
    lines.append(f"--- STEP 3: SQL RESULTS (real data, {row_count} rows) ---")
    lines.append(_format_rows(real_rows))

    # --- STEP 4: DATA SENT TO LLM (after column masking) ---
    lines.append("")
    lines.append("--- STEP 4: DATA SENT TO LLM (after column masking) ---")
    if masked_results and masked_results.get("rows"):
        # Identify which columns were actually masked
        masked_cols: List[str] = []
        if masked_results["rows"]:
            first = masked_results["rows"][0]
            masked_cols = [c for c in masked_results.get("columns", [])
                           if first.get(c) == "[MASKED]"]
        if masked_cols:
            lines.append(f"  Masked columns: {', '.join(masked_cols)}")
        else:
            lines.append("  (no columns masked — data identical to Step 3)")
        lines.append(_format_rows(masked_results.get("rows")))
    elif results and results.get("rows"):
        lines.append("  (no column masking applied — data identical to Step 3)")
        lines.append(_format_rows(real_rows))
    else:
        lines.append("  (no data)")

    # --- STEP 5: LLM SUMMARY OUTPUT ---
    lines.append("")
    lines.append("--- STEP 5: LLM SUMMARY OUTPUT ---")
    lines.append(f'"{summary}"' if summary else "(no summary)")

    lines.append("")
    lines.append(sep)

    _logger.info("\n".join(lines))
