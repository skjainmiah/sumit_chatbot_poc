"""PII Masking - masks sensitive information before sending to LLM."""
import re
import json
import sqlite3
import logging
from typing import Dict, Tuple, List, Optional

logger = logging.getLogger("chatbot.pii")

# Default PII patterns with display labels
DEFAULT_PII_PATTERNS = {
    'EMAIL': {
        'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'label': 'Email Addresses',
        'enabled': True,
    },
    'PHONE': {
        'pattern': r'\b(?:\+1[-.]?)?\(?[0-9]{3}\)?[-.]?[0-9]{3}[-.]?[0-9]{4}\b',
        'label': 'Phone Numbers',
        'enabled': True,
    },
    'SSN': {
        'pattern': r'\b\d{3}-\d{2}-\d{4}\b',
        'label': 'Social Security Numbers',
        'enabled': True,
    },
    'PASSPORT': {
        'pattern': r'\b[A-Z]{1,2}[0-9]{6,9}\b',
        'label': 'Passport Numbers',
        'enabled': True,
    },
    'CREDIT_CARD': {
        'pattern': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'label': 'Credit Card Numbers',
        'enabled': True,
    },
    'EMPLOYEE_ID': {
        'pattern': r'\b[A-Z]{1,4}-\d{3,6}\b',
        'label': 'Employee IDs',
        'enabled': True,
    },
}


def _get_app_db_path() -> str:
    """Get path to app database."""
    from backend.config import settings
    return settings.app_db_path


def _ensure_pii_settings_table():
    """Create the pii_settings table if it doesn't exist."""
    try:
        conn = sqlite3.connect(_get_app_db_path())
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pii_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Could not create pii_settings table: {e}")


def get_pii_settings() -> Dict:
    """Load PII settings from database. Returns dict with 'enabled', 'log_enabled', 'patterns'."""
    from backend.config import settings as app_settings

    defaults = {
        'enabled': app_settings.PII_MASKING_ENABLED,
        'log_enabled': app_settings.PII_LOG_ENABLED,
        'patterns': {k: v['enabled'] for k, v in DEFAULT_PII_PATTERNS.items()},
    }

    try:
        _ensure_pii_settings_table()
        conn = sqlite3.connect(_get_app_db_path())
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM pii_settings")
        rows = cursor.fetchall()
        conn.close()

        db_settings = {row[0]: row[1] for row in rows}

        if 'pii_enabled' in db_settings:
            defaults['enabled'] = db_settings['pii_enabled'] == 'true'
        if 'pii_log_enabled' in db_settings:
            defaults['log_enabled'] = db_settings['pii_log_enabled'] == 'true'
        if 'pii_patterns' in db_settings:
            try:
                pattern_config = json.loads(db_settings['pii_patterns'])
                defaults['patterns'].update(pattern_config)
            except (json.JSONDecodeError, TypeError):
                pass

    except Exception as e:
        logger.warning(f"Could not load PII settings from DB, using defaults: {e}")

    return defaults


def save_pii_settings(enabled: bool, log_enabled: bool, patterns: Dict[str, bool]):
    """Save PII settings to database."""
    try:
        _ensure_pii_settings_table()
        conn = sqlite3.connect(_get_app_db_path())
        cursor = conn.cursor()

        settings_to_save = {
            'pii_enabled': 'true' if enabled else 'false',
            'pii_log_enabled': 'true' if log_enabled else 'false',
            'pii_patterns': json.dumps(patterns),
        }

        for key, value in settings_to_save.items():
            cursor.execute(
                "INSERT OR REPLACE INTO pii_settings (key, value) VALUES (?, ?)",
                (key, value)
            )

        conn.commit()
        conn.close()
        logger.info(f"PII settings saved: enabled={enabled}, log={log_enabled}, patterns={patterns}")
    except Exception as e:
        logger.error(f"Failed to save PII settings: {e}")
        raise


class PIIMasker:
    """Masks PII in text using regex patterns."""

    def __init__(self):
        self.token_map: Dict[str, str] = {}
        self.counters = {}

    def _get_active_patterns(self) -> Dict[str, str]:
        """Get currently active PII patterns based on settings."""
        pii_settings = get_pii_settings()
        pattern_config = pii_settings.get('patterns', {})

        active = {}
        for pii_type, info in DEFAULT_PII_PATTERNS.items():
            if pattern_config.get(pii_type, info['enabled']):
                active[pii_type] = info['pattern']
        return active

    def _get_token(self, pii_type: str) -> str:
        """Generate a unique token for a PII type."""
        if pii_type not in self.counters:
            self.counters[pii_type] = 0
        self.counters[pii_type] += 1
        return f"[{pii_type}_{self.counters[pii_type]}]"

    def mask(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Mask PII in text and return masked text with token map."""
        self.token_map = {}
        self.counters = {}

        # Check if PII masking is enabled
        pii_settings = get_pii_settings()
        if not pii_settings.get('enabled', True):
            return text, {}

        active_patterns = self._get_active_patterns()
        masked_text = text

        for pii_type, pattern in active_patterns.items():
            matches = re.findall(pattern, masked_text, re.IGNORECASE)
            for match in set(matches):
                token = self._get_token(pii_type)
                self.token_map[token] = match
                masked_text = masked_text.replace(match, token)

        return masked_text, self.token_map

    def unmask(self, text: str, token_map: Dict[str, str]) -> str:
        """Restore original PII values from tokens."""
        unmasked_text = text
        for token, original in token_map.items():
            unmasked_text = unmasked_text.replace(token, original)
        return unmasked_text


class PIIDetector:
    """Detects if text contains PII."""

    def __init__(self):
        self.masker = PIIMasker()

    def contains_pii(self, text: str) -> bool:
        """Check if text contains PII."""
        masked, token_map = self.masker.mask(text)
        return len(token_map) > 0

    def get_pii_types(self, text: str) -> List[str]:
        """Get list of PII types found in text."""
        pii_types = []
        active_patterns = self.masker._get_active_patterns()
        for pii_type, pattern in active_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                pii_types.append(pii_type)
        return pii_types


# Singleton instances
_masker: PIIMasker = None


def get_masker() -> PIIMasker:
    """Get PII masker singleton."""
    global _masker
    if _masker is None:
        _masker = PIIMasker()
    return _masker


def mask_pii(text: str) -> Tuple[str, Dict[str, str]]:
    """Convenience function to mask PII."""
    masker = get_masker()
    return masker.mask(text)


def unmask_pii(text: str, token_map: Dict[str, str]) -> str:
    """Convenience function to unmask PII."""
    masker = get_masker()
    return masker.unmask(text, token_map)
