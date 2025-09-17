from typing import List, Optional
import time

from openai import OpenAI

from config_manager import secrets


class EmbeddingGenerator:
    """
    Minimal embedding generator using OpenAI API.

    Generates embeddings for batches of texts. Designed for post-sync usage to
    embed product names and store them in the database.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or secrets.OPENAI_API_KEY
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        self.max_retries = 3
        self.base_delay = 1.0

    def generate(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # Filter invalid texts
        batch = [t for t in texts if t and t.strip()]
        if not batch:
            return []
        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(model=self.model, input=batch)
                return [item.embedding for item in response.data]
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay * (2 ** attempt))
                else:
                    raise

    def get_embedding_dimension(self) -> int:
        model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return model_dimensions.get(self.model, 1536)


