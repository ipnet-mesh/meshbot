"""Knowledge base system for local text file serving and RAG."""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeChunk:
    """A chunk of knowledge from the knowledge base."""

    content: str
    source_file: str
    chunk_id: str
    metadata: Dict[str, Any]


@dataclass
class SearchResult:
    """Result from knowledge base search."""

    chunk: KnowledgeChunk
    score: float
    excerpt: str


class SimpleKnowledgeBase:
    """Simple text-based knowledge base without vector search."""

    def __init__(self, knowledge_dir: Path):
        self.knowledge_dir = Path(knowledge_dir)
        self._chunks: List[KnowledgeChunk] = []
        self._file_index: Dict[str, List[KnowledgeChunk]] = {}
        self._word_index: Dict[str, List[KnowledgeChunk]] = {}
        self._loaded = False

    async def load(self) -> None:
        """Load all text files from knowledge directory."""
        if self._loaded:
            return

        logger.info(f"Loading knowledge base from {self.knowledge_dir}")

        if not self.knowledge_dir.exists():
            logger.warning(f"Knowledge directory {self.knowledge_dir} does not exist")
            return

        # Clear existing data
        self._chunks.clear()
        self._file_index.clear()
        self._word_index.clear()

        # Load all text files
        text_extensions = {".txt", ".md", ".rst", ".py", ".js", ".html", ".css"}

        for file_path in self.knowledge_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in text_extensions:
                await self._load_file(file_path)

        # Build word index for simple search
        await self._build_word_index()

        self._loaded = True
        logger.info(
            f"Loaded {len(self._chunks)} knowledge chunks from {len(self._file_index)} files"
        )

    async def _load_file(self, file_path: Path) -> None:
        """Load a single file and split into chunks."""
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()

            # Split content into chunks (paragraphs or sections)
            chunks = self._split_content(
                content, str(file_path.relative_to(self.knowledge_dir))
            )

            self._file_index[str(file_path)] = chunks
            self._chunks.extend(chunks)

        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}")

    def _split_content(self, content: str, source_file: str) -> List[KnowledgeChunk]:
        """Split content into manageable chunks."""
        chunks = []

        # Split by double newlines (paragraphs) or by lines if no paragraphs
        paragraphs = re.split(r"\n\s*\n", content)
        if len(paragraphs) == 1:
            # No clear paragraphs, split by lines
            paragraphs = content.split("\n")

        current_chunk = ""
        chunk_id = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # If adding this paragraph would make chunk too large, save current chunk
            if len(current_chunk) + len(paragraph) > 1000 and current_chunk:
                chunk = KnowledgeChunk(
                    content=current_chunk.strip(),
                    source_file=source_file,
                    chunk_id=f"{source_file}:{chunk_id}",
                    metadata={"file": source_file, "chunk_id": chunk_id},
                )
                chunks.append(chunk)
                current_chunk = paragraph
                chunk_id += 1
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph

        # Add the last chunk if there's content
        if current_chunk.strip():
            chunk = KnowledgeChunk(
                content=current_chunk.strip(),
                source_file=source_file,
                chunk_id=f"{source_file}:{chunk_id}",
                metadata={"file": source_file, "chunk_id": chunk_id},
            )
            chunks.append(chunk)

        return chunks

    async def _build_word_index(self) -> None:
        """Build a simple word index for search."""
        for chunk in self._chunks:
            # Extract words (simple tokenization)
            words = re.findall(r"\b\w+\b", chunk.content.lower())

            for word in set(words):  # Use set to avoid duplicates
                if word not in self._word_index:
                    self._word_index[word] = []
                self._word_index[word].append(chunk)

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search the knowledge base."""
        if not self._loaded:
            await self.load()

        # Simple keyword-based search
        query_words = re.findall(r"\b\w+\b", query.lower())
        if not query_words:
            return []

        # Find chunks containing query words
        chunk_scores: Dict[KnowledgeChunk, float] = {}

        for word in query_words:
            if word in self._word_index:
                for chunk in self._word_index[word]:
                    # Score based on word frequency and position
                    word_count = chunk.content.lower().count(word)
                    score = word_count / len(chunk.content.split())

                    if chunk in chunk_scores:
                        chunk_scores[chunk] += score
                    else:
                        chunk_scores[chunk] = score

        # Sort by score and create results
        sorted_chunks = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for chunk, score in sorted_chunks[:max_results]:
            # Create excerpt with highlighted query
            excerpt = self._create_excerpt(chunk.content, query_words)

            result = SearchResult(chunk=chunk, score=score, excerpt=excerpt)
            results.append(result)

        return results

    def _create_excerpt(
        self, content: str, query_words: List[str], max_length: int = 200
    ) -> str:
        """Create an excerpt with query words highlighted."""
        # Find the best sentence containing query words
        sentences = re.split(r"[.!?]+", content)
        best_sentence = ""
        best_score = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Score sentence based on query word matches
            score = sum(1 for word in query_words if word in sentence.lower())
            if score > best_score:
                best_score = score
                best_sentence = sentence

        if not best_sentence:
            # Fallback to first part of content
            excerpt = (
                content[:max_length] + "..." if len(content) > max_length else content
            )
        else:
            excerpt = (
                best_sentence[:max_length] + "..."
                if len(best_sentence) > max_length
                else best_sentence
            )

        # Simple highlighting (in a real system, you'd use proper markup)
        for word in query_words:
            excerpt = re.sub(
                f"({re.escape(word)})", r"**\1**", excerpt, flags=re.IGNORECASE
            )

        return excerpt

    async def get_file_content(self, file_path: str) -> Optional[str]:
        """Get full content of a specific file."""
        full_path = self.knowledge_dir / file_path
        if not full_path.exists():
            return None

        try:
            async with aiofiles.open(full_path, "r", encoding="utf-8") as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None

    async def list_files(self) -> List[str]:
        """List all files in the knowledge base."""
        if not self._loaded:
            await self.load()

        return list(self._file_index.keys())

    async def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        if not self._loaded:
            await self.load()

        total_chunks = len(self._chunks)
        total_files = len(self._file_index)
        total_words = len(self._word_index)

        # Calculate average chunk size
        if total_chunks > 0:
            avg_chunk_size = (
                sum(len(chunk.content) for chunk in self._chunks) / total_chunks
            )
        else:
            avg_chunk_size = 0

        return {
            "total_files": total_files,
            "total_chunks": total_chunks,
            "total_unique_words": total_words,
            "average_chunk_size": avg_chunk_size,
            "knowledge_directory": str(self.knowledge_dir),
        }


class VectorKnowledgeBase(SimpleKnowledgeBase):
    """Knowledge base with vector search capabilities."""

    def __init__(self, knowledge_dir: Path):
        super().__init__(knowledge_dir)
        self._embeddings = None
        self._embedding_model = None
        self._vector_index = None

    async def _load_embeddings(self) -> None:
        """Load sentence transformer model for embeddings."""
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np

            logger.info("Loading sentence transformer model...")
            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Model loaded successfully")

        except ImportError:
            logger.warning(
                "sentence-transformers not available, falling back to simple search"
            )
            return
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
            return

    async def _build_vector_index(self) -> None:
        """Build vector index for similarity search."""
        if not self._embedding_model or not self._chunks:
            return

        try:
            import numpy as np

            logger.info("Building vector index...")
            texts = [chunk.content for chunk in self._chunks]
            self._embeddings = self._embedding_model.encode(texts)
            logger.info(f"Built vector index with {len(self._embeddings)} embeddings")

        except Exception as e:
            logger.error(f"Error building vector index: {e}")

    async def load(self) -> None:
        """Load knowledge base with vector capabilities."""
        await super().load()

        if self._chunks:
            await self._load_embeddings()
            if self._embedding_model:
                await self._build_vector_index()

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search using vector similarity if available, otherwise fallback to simple search."""
        if self._embeddings is not None and self._embedding_model is not None:
            return await self._vector_search(query, max_results)
        else:
            return await super().search(query, max_results)

    async def _vector_search(self, query: str, max_results: int) -> List[SearchResult]:
        """Perform vector similarity search."""
        try:
            import numpy as np

            # Encode query
            query_embedding = self._embedding_model.encode([query])

            # Calculate similarities
            from sklearn.metrics.pairwise import cosine_similarity

            similarities = cosine_similarity(query_embedding, self._embeddings)[0]

            # Get top results
            top_indices = np.argsort(similarities)[::-1][:max_results]

            results = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    chunk = self._chunks[idx]
                    excerpt = self._create_excerpt(chunk.content, query.split())

                    result = SearchResult(
                        chunk=chunk, score=float(similarities[idx]), excerpt=excerpt
                    )
                    results.append(result)

            return results

        except ImportError:
            logger.warning("scikit-learn not available, falling back to simple search")
            return await super().search(query, max_results)
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return await super().search(query, max_results)


def create_knowledge_base(
    knowledge_dir: Path, use_vectors: bool = False
) -> SimpleKnowledgeBase:
    """Factory function to create appropriate knowledge base."""
    if use_vectors:
        return VectorKnowledgeBase(knowledge_dir)
    else:
        return SimpleKnowledgeBase(knowledge_dir)
