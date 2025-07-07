"""
Embedding generation module using OpenAI API.

This module provides the OpenAIEmbeddingGenerator class for generating
vector embeddings from product text data using OpenAI's embedding models.
"""
from typing import List, Optional, Dict, Any
import time
import structlog
from openai import OpenAI
from openai.types import CreateEmbeddingResponse

from .config import config

logger = structlog.get_logger(__name__)


class OpenAIEmbeddingGenerator:
    """
    OpenAI embedding generator for product text vectorization.
    
    This class handles batch generation of embeddings using OpenAI's API
    with proper error handling, rate limiting, and retry logic.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        """
        Initialize the OpenAI embedding generator.
        
        Args:
            api_key: OpenAI API key. If None, uses config.
            model: OpenAI embedding model to use.
        """
        self.api_key = api_key or config.get_openai_api_key()
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        self.logger = logger.bind(component="embedding_generator")
        
        # Rate limiting and retry configuration
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_batch_size = 100  # OpenAI's recommended batch size
        self.max_tokens_per_request = 8000  # Conservative limit
        
        self.logger.info(
            "OpenAI embedding generator initialized",
            model=self.model,
            max_batch_size=self.max_batch_size
        )
    
    def generate(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to generate embeddings for.
            
        Returns:
            List of embedding vectors (each vector is a list of floats).
            
        Raises:
            RuntimeError: If embedding generation fails after all retries.
        """
        if not texts:
            self.logger.warning("Empty text list provided")
            return []
        
        self.logger.info(
            "Starting embedding generation",
            total_texts=len(texts),
            model=self.model
        )
        
        try:
            # Filter out empty or None texts
            valid_texts = [text for text in texts if text and text.strip()]
            
            if len(valid_texts) != len(texts):
                self.logger.warning(
                    "Filtered out empty texts",
                    original_count=len(texts),
                    valid_count=len(valid_texts)
                )
            
            if not valid_texts:
                self.logger.error("No valid texts to process")
                return []
            
            # Process texts in batches
            all_embeddings = []
            batches = self._create_batches(valid_texts)
            
            for i, batch in enumerate(batches):
                self.logger.info(
                    f"Processing batch {i + 1}/{len(batches)}",
                    batch_size=len(batch)
                )
                
                batch_embeddings = self._generate_batch_embeddings(batch)
                all_embeddings.extend(batch_embeddings)
                
                # Rate limiting: small delay between batches
                if i < len(batches) - 1:  # Don't delay after the last batch
                    time.sleep(0.5)
            
            self.logger.info(
                "Embedding generation completed",
                total_embeddings=len(all_embeddings)
            )
            
            return all_embeddings
            
        except Exception as e:
            self.logger.error(
                "Failed to generate embeddings",
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Embedding generation failed: {str(e)}") from e
    
    def _create_batches(self, texts: List[str]) -> List[List[str]]:
        """
        Create batches of texts for API calls.
        
        Args:
            texts: List of texts to batch.
            
        Returns:
            List of text batches.
        """
        batches = []
        current_batch = []
        current_tokens = 0
        
        for text in texts:
            # Rough token estimate (4 characters per token)
            estimated_tokens = len(text) // 4
            
            # Check if adding this text would exceed limits
            if (len(current_batch) >= self.max_batch_size or 
                current_tokens + estimated_tokens > self.max_tokens_per_request):
                
                if current_batch:  # Don't add empty batches
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
            
            current_batch.append(text)
            current_tokens += estimated_tokens
        
        # Add the last batch if it's not empty
        if current_batch:
            batches.append(current_batch)
        
        self.logger.debug(
            "Created batches",
            total_batches=len(batches),
            avg_batch_size=sum(len(batch) for batch in batches) / len(batches) if batches else 0
        )
        
        return batches
    
    def _generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a single batch of texts with retry logic.
        
        Args:
            texts: Batch of texts to process.
            
        Returns:
            List of embedding vectors for the batch.
        """
        for attempt in range(self.max_retries):
            try:
                response: CreateEmbeddingResponse = self.client.embeddings.create(
                    input=texts,
                    model=self.model
                )
                
                # Extract embeddings from response
                embeddings = [embedding.embedding for embedding in response.data]
                
                self.logger.debug(
                    "Batch embeddings generated successfully",
                    batch_size=len(texts),
                    embedding_dimension=len(embeddings[0]) if embeddings else 0
                )
                
                return embeddings
                
            except Exception as e:
                self.logger.warning(
                    f"Attempt {attempt + 1} failed for batch embedding",
                    error=str(e),
                    batch_size=len(texts)
                )
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.base_delay * (2 ** attempt)
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    self.logger.error(
                        "All retry attempts failed for batch embedding",
                        batch_size=len(texts),
                        error=str(e)
                    )
                    raise
        
        # This should not be reached, but included for completeness
        raise RuntimeError("Unexpected error in batch embedding generation")
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings for the current model.
        
        Returns:
            Embedding dimension.
        """
        # Known dimensions for OpenAI models
        model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        
        dimension = model_dimensions.get(self.model, 1536)
        self.logger.debug(f"Embedding dimension for {self.model}: {dimension}")
        return dimension
    
    def test_connection(self) -> bool:
        """
        Test the OpenAI API connection with a simple embedding request.
        
        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            self.logger.info("Testing OpenAI API connection...")
            
            test_embedding = self.generate(["Test connection"])
            
            if test_embedding and len(test_embedding) == 1:
                self.logger.info(
                    "OpenAI API connection test successful",
                    embedding_dimension=len(test_embedding[0])
                )
                return True
            else:
                self.logger.error("OpenAI API connection test failed - invalid response")
                return False
                
        except Exception as e:
            self.logger.error(
                "OpenAI API connection test failed",
                error=str(e)
            )
            return False

# Alias for backward compatibility and consistent naming
EmbeddingGenerator = OpenAIEmbeddingGenerator

# Also export both names
__all__ = ["OpenAIEmbeddingGenerator", "EmbeddingGenerator"] 