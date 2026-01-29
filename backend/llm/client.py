"""LLM client - uses company API (Coforge/Quasar) only via REST calls."""
import time
import logging
import requests
import urllib3
from typing import Optional, List
from backend.config import settings

logger = logging.getLogger("chatbot.llm.client")

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

    def _request_with_fallback(self, primary_url: str, fallback_url: str, payload: dict, call_type: str = "unknown") -> dict:
        """Make REST request with v2→v3 fallback."""
        start = time.time()
        model_used = payload.get("model", "N/A")
        try:
            logger.info(f"[{call_type}] POST {primary_url} | model={model_used}")
            response = requests.post(
                primary_url,
                headers=self._headers(),
                json=payload,
                timeout=120,
                verify=self.verify_ssl,
                proxies=self.proxies
            )
            elapsed_ms = int((time.time() - start) * 1000)
            logger.info(f"[{call_type}] Response status={response.status_code} | {elapsed_ms}ms")
            if response.status_code >= 400:
                logger.error(f"[{call_type}] HTTP {response.status_code} from {primary_url} | body={response.text[:500]}")
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.warning(f"[{call_type}] Primary request failed after {elapsed_ms}ms: {e}")
            if not fallback_url:
                logger.error(f"[{call_type}] No fallback URL configured, raising error")
                raise
            logger.info(f"[{call_type}] Falling back to v3: {fallback_url}")
            fallback_start = time.time()
            response = requests.post(
                fallback_url,
                headers=self._headers(),
                json=payload,
                timeout=120,
                verify=self.verify_ssl,
                proxies=self.proxies
            )
            fallback_ms = int((time.time() - fallback_start) * 1000)
            logger.info(f"[{call_type}] Fallback response status={response.status_code} | {fallback_ms}ms")
            if response.status_code >= 400:
                logger.error(f"[{call_type}] Fallback HTTP {response.status_code} | body={response.text[:500]}")
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
        model_name = self.fast_model if use_fast_model else self.model
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        # Log the system prompt size and user message preview
        sys_msg = next((m for m in messages if m.get("role") == "system"), None)
        user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        sys_len = len(sys_msg["content"]) if sys_msg else 0
        user_preview = (user_msg["content"][:120] + "...") if user_msg and len(user_msg["content"]) > 120 else (user_msg["content"] if user_msg else "N/A")
        logger.info(f"[chat_completion] model={model_name} json_mode={json_mode} sys_prompt_chars={sys_len} user_preview=\"{user_preview}\"")

        start = time.time()
        try:
            data = self._request_with_fallback(self.chat_url, self.chat_url_v3, payload, call_type="chat_completion")
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.error(f"[chat_completion] FAILED after {elapsed_ms}ms: {type(e).__name__}: {e}")
            raise

        elapsed_ms = int((time.time() - start) * 1000)

        # Handle response formats
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"]
            logger.info(f"[chat_completion] OK {elapsed_ms}ms | response_chars={len(content)}")
            return content
        elif "response" in data:
            logger.info(f"[chat_completion] OK {elapsed_ms}ms | response_chars={len(data['response'])}")
            return data["response"]
        elif "content" in data:
            logger.info(f"[chat_completion] OK {elapsed_ms}ms | response_chars={len(data['content'])}")
            return data["content"]
        else:
            logger.error(f"[chat_completion] Unexpected response format after {elapsed_ms}ms: {str(data)[:300]}")
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
        logger.info(f"[embedding] Single text, chars={len(text)}")
        return self.generate_embeddings_batch([text])[0]

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts via REST API."""
        logger.info(f"[embedding_batch] {len(texts)} texts, total_chars={sum(len(t) for t in texts)}")
        payload = {
            "model": self.embedding_model,
            "texts": texts,
            "dimensions": self.embedding_dimensions
        }

        start = time.time()
        try:
            data = self._request_with_fallback(self.embedding_url, self.embedding_url_v3, payload, call_type="embedding")
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.error(f"[embedding] FAILED after {elapsed_ms}ms: {type(e).__name__}: {e}")
            raise

        elapsed_ms = int((time.time() - start) * 1000)

        # Handle response formats
        if "data" in data:
            result = [item["embedding"] for item in data["data"]]
            logger.info(f"[embedding] OK {elapsed_ms}ms | {len(result)} embeddings, dims={len(result[0]) if result else 0}")
            return result
        elif isinstance(data, list):
            logger.info(f"[embedding] OK {elapsed_ms}ms | {len(data)} embeddings")
            return data
        else:
            logger.error(f"[embedding] Unexpected response format after {elapsed_ms}ms: {str(data)[:300]}")
            raise ValueError(f"Unexpected embedding response format: {data}")


# Singleton
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
