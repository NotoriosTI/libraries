from typing import List, Optional
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        # Tunable performance parameters
        self.max_batch_size = 300  # increase from 100 to 300
        self.max_workers = 3  # parallelize up to 3 concurrent batches

    def generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using parallelized batch requests.

        This method creates batches up to `self.max_batch_size` and submits multiple
        batches concurrently using a ThreadPoolExecutor with `self.max_workers`.
        """
        if not texts:
            return []

        # Filter invalid texts
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return []

        # Create batches
        batches = []
        current = []
        for t in valid_texts:
            current.append(t)
            if len(current) >= self.max_batch_size:
                batches.append(current)
                current = []
        if current:
            batches.append(current)

        # Helper to generate a single batch with retries
        def _gen_batch(batch_texts: List[str]):
            for attempt in range(self.max_retries):
                try:
                    resp = self.client.embeddings.create(model=self.model, input=batch_texts)
                    return [item.embedding for item in resp.data]
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.base_delay * (2 ** attempt))
                    else:
                        raise

        results: List[List[float]] = []

        # Parallelize batch requests
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(_gen_batch, b): i for i, b in enumerate(batches)}
            for fut in as_completed(futures):
                batch_res = fut.result()
                results.extend(batch_res)

        return results

    def get_embedding_dimension(self) -> int:
        model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return model_dimensions.get(self.model, 1536)


