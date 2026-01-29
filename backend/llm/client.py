"""LLM client - uses company API (Coforge/Quasar) only via REST calls."""
import requests
import urllib3
from typing import Optional, List
from backend.config import settings

# Disable SSL warnings for corporate environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class LLMClient:
    """REST-based LLM client for Coforge/Quasar API. No OpenAI SDK dependency."""

    def __init__(self):
        self.chat_url = settings.LLM_CHAT_URL
        self.chat_url_v3 = settings.LLM_CHAT_URL_V3
        self.embedding_url = settings.LLM_EMBEDDING_URL
        self.embedding_url_v3 = settings.LLM_EMBEDDING_URL_V3
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.fast_model = settings.LLM_FAST_MODEL
        self.embedding_model = settings.EMBEDDING_MODEL
        self.embedding_dimensions = settings.EMBEDDING_DIMENSIONS
        self.verify_ssl = settings.LLM_VERIFY_SSL
        self.proxy = settings.LLM_PROXY
        self.proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None

        # Validate configuration
        if not self.chat_url:
            raise RuntimeError("LLM_CHAT_URL not configured in .env")
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY not configured in .env")

        print(f"LLM Client: Chat API at {self.chat_url}")
        print(f"LLM Client: Embedding API at {self.embedding_url}")
        if self.chat_url_v3:
            print(f"LLM Client: Chat fallback at {self.chat_url_v3}")
        if self.embedding_url_v3:
            print(f"LLM Client: Embedding fallback at {self.embedding_url_v3}")
        if not self.verify_ssl:
            print("  SSL verification: disabled")
        if self.proxy:
            print(f"  Proxy: {self.proxy}")

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-API-KEY": self.api_key
        }

    def _request_with_fallback(self, primary_url: str, fallback_url: str, payload: dict) -> dict:
        """Make REST request with v2→v3 fallback."""
        try:
            response = requests.post(
                primary_url,
                headers=self._headers(),
                json=payload,
                timeout=120,
                verify=self.verify_ssl,
                proxies=self.proxies
            )
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
            if not fallback_url:
                raise
            print(f"  v2 request failed ({e}), falling back to v3: {fallback_url}")
            response = requests.post(
                fallback_url,
                headers=self._headers(),
                json=payload,
                timeout=120,
                verify=self.verify_ssl,
                proxies=self.proxies
            )
            response.raise_for_status()
            return response.json()

    def chat_completion(
        self,
        messages: List[dict],
        temperature: float = 0.0,
        max_tokens: int = 2000,
        json_mode: bool = False,
        use_fast_model: bool = False,
        top_p: float = 0.9
    ) -> str:
        """Generate chat completion via REST API."""
        payload = {
            "model": self.fast_model if use_fast_model else self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        data = self._request_with_fallback(self.chat_url, self.chat_url_v3, payload)

        # Handle response formats
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        elif "response" in data:
            return data["response"]
        elif "content" in data:
            return data["content"]
        else:
            raise ValueError(f"Unexpected response format: {data}")

    def chat_completion_with_usage(
        self,
        messages: List[dict],
        temperature: float = 0.0,
        max_tokens: int = 2000,
        json_mode: bool = False
    ) -> tuple:
        """Generate chat completion and return usage info."""
        content = self.chat_completion(messages, temperature, max_tokens, json_mode)
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return content, usage

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text via REST API."""
        return self.generate_embeddings_batch([text])[0]

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts via REST API."""
        payload = {
            "model": self.embedding_model,
            "texts": texts,
            "dimensions": self.embedding_dimensions
        }

        data = self._request_with_fallback(self.embedding_url, self.embedding_url_v3, payload)

        # Handle response formats
        if "data" in data:
            return [item["embedding"] for item in data["data"]]
        elif isinstance(data, list):
            return data
        else:
            raise ValueError(f"Unexpected embedding response format: {data}")


# Singleton
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
