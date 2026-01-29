"""PII Masking - masks sensitive information before sending to LLM."""
import re
from typing import Dict, Tuple, List
import uuid


class PIIMasker:
    """Masks PII in text using regex patterns."""

    def __init__(self):
        # Mapping of masked tokens to original values
        self.token_map: Dict[str, str] = {}

        # PII patterns
        self.patterns = {
            'EMAIL': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'PHONE': r'\b(?:\+1[-.]?)?\(?[0-9]{3}\)?[-.]?[0-9]{3}[-.]?[0-9]{4}\b',
            'SSN': r'\b\d{3}-\d{2}-\d{4}\b',
            'PASSPORT': r'\b[A-Z]{1,2}[0-9]{6,9}\b',
            'CREDIT_CARD': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            'EMPLOYEE_ID': r'\bAA-\d{5,6}\b',
        }

        self.counters = {}

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
        masked_text = text

        for pii_type, pattern in self.patterns.items():
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
        for pii_type, pattern in self.masker.patterns.items():
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
