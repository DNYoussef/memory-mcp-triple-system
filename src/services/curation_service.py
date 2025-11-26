"""
Curation Service
Business logic for memory chunk curation, lifecycle tagging, and verification.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import uuid
from loguru import logger

from ..cache.memory_cache import MemoryCache


class CurationService:
    """Service for curating memory chunks with lifecycle tags and verification."""

    # Lifecycle tag constants
    LIFECYCLE_PERMANENT = 'permanent'
    LIFECYCLE_TEMPORARY = 'temporary'
    LIFECYCLE_EPHEMERAL = 'ephemeral'
    VALID_LIFECYCLES = {LIFECYCLE_PERMANENT, LIFECYCLE_TEMPORARY, LIFECYCLE_EPHEMERAL}

    def __init__(
        self,
        chroma_client,
        collection_name: str = "memory_chunks",
        data_dir: str = "./data"
    ):
        """
        Initialize curation service.

        Args:
            chroma_client: ChromaDB client instance
            collection_name: Collection name
            data_dir: Directory for data files (time logs)
        """
        if chroma_client is None:
            raise ValueError("chroma_client cannot be None")
        if not isinstance(collection_name, str):
            raise ValueError("collection_name must be string")
        if not isinstance(data_dir, str):
            raise ValueError("data_dir must be string")

        self.client = chroma_client
        self.collection_name = collection_name
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Preferences cache (30-day TTL)
        self.preferences_cache = MemoryCache(
            ttl_seconds=30 * 24 * 3600,
            max_size=1000
        )

        # Get or create collection
        try:
            self.collection = self.client.get_collection(collection_name)
            logger.info(f"Using existing collection: {collection_name}")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {collection_name}")

    def get_unverified_chunks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get batch of unverified chunks for curation.

        Args:
            limit: Number of chunks to retrieve

        Returns:
            List of chunk dictionaries
        """
        if limit <= 0:
            raise ValueError("limit must be positive")
        if limit > 100:
            raise ValueError("limit too large (max 100)")

        # Query ChromaDB for unverified chunks
        results = self.collection.get(
            where={"verified": False},
            limit=limit
        )

        # Format results
        chunks = []
        if results['ids']:
            for i in range(len(results['ids'])):
                chunks.append({
                    'id': results['ids'][i],
                    'text': results['documents'][i] if results['documents'] else '',
                    'metadata': results['metadatas'][i] if results['metadatas'] else {},
                    'file_path': (
                        results['metadatas'][i].get('file_path', '')
                        if results['metadatas'] else ''
                    ),
                    'chunk_index': (
                        results['metadatas'][i].get('chunk_index', 0)
                        if results['metadatas'] else 0
                    ),
                    'lifecycle': (
                        results['metadatas'][i].get('lifecycle', 'temporary')
                        if results['metadatas'] else 'temporary'
                    ),
                    'verified': (
                        results['metadatas'][i].get('verified', False)
                        if results['metadatas'] else False
                    )
                })

        logger.info(f"Retrieved {len(chunks)} unverified chunks")
        return chunks

    def tag_lifecycle(self, chunk_id: str, lifecycle: str) -> bool:
        """
        Tag chunk with lifecycle label.

        Args:
            chunk_id: Chunk ID
            lifecycle: Lifecycle tag (permanent/temporary/ephemeral)

        Returns:
            True if successful
        """
        if not isinstance(chunk_id, str):
            raise ValueError("chunk_id must be string")
        if lifecycle not in self.VALID_LIFECYCLES:
            raise ValueError(f"Invalid lifecycle: {lifecycle}")

        try:
            # Update metadata in ChromaDB
            self.collection.update(
                ids=[chunk_id],
                metadatas=[{
                    'lifecycle': lifecycle,
                    'updated_at': datetime.now().isoformat()
                }]
            )

            logger.info(f"Tagged chunk {chunk_id} as {lifecycle}")
            return True
        except Exception as e:
            logger.error(f"Failed to tag chunk {chunk_id}: {e}")
            return False

    def mark_verified(self, chunk_id: str) -> bool:
        """
        Mark chunk as verified.

        Args:
            chunk_id: Chunk ID

        Returns:
            True if successful
        """
        if not isinstance(chunk_id, str):
            raise ValueError("chunk_id must be string")

        try:
            # Update metadata in ChromaDB
            self.collection.update(
                ids=[chunk_id],
                metadatas=[{
                    'verified': True,
                    'verified_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }]
            )

            logger.info(f"Marked chunk {chunk_id} as verified")
            return True
        except Exception as e:
            logger.error(f"Failed to verify chunk {chunk_id}: {e}")
            return False

    def log_time(
        self,
        duration_seconds: int,
        chunks_curated: int = 0,
        session_id: Optional[str] = None
    ) -> None:
        """
        Log curation session time.

        Args:
            duration_seconds: Session duration in seconds
            chunks_curated: Number of chunks curated
            session_id: Optional session ID (generated if not provided)
        """
        if duration_seconds < 0:
            raise ValueError("duration must be non-negative")
        if chunks_curated < 0:
            raise ValueError("chunks_curated must be non-negative")

        log_file = self.data_dir / 'curation_time.json'
        session_id = session_id or str(uuid.uuid4())

        # Load existing log
        if log_file.exists():
            with open(log_file, 'r') as f:
                log = json.load(f)
        else:
            log = {'sessions': [], 'stats': {}}

        # Add session
        log['sessions'].append({
            'session_id': session_id,
            'date': datetime.now().isoformat(),
            'duration_seconds': duration_seconds,
            'chunks_curated': chunks_curated
        })

        # Update stats
        log['stats'] = self._calculate_stats(log['sessions'])

        # Save
        with open(log_file, 'w') as f:
            json.dump(log, f, indent=2)

        logger.info(f"Logged session {session_id}: {duration_seconds}s, {chunks_curated} chunks")

    def _calculate_stats(self, sessions: List[Dict]) -> Dict[str, Any]:
        """
        Calculate statistics from session logs.

        Args:
            sessions: List of session dictionaries

        Returns:
            Statistics dictionary
        """
        if not sessions:
            return {
                'total_time_minutes': 0,
                'avg_time_per_day': 0,
                'days_active': 0,
                'total_chunks': 0
            }

        total_seconds = sum(s['duration_seconds'] for s in sessions)
        total_chunks = sum(s.get('chunks_curated', 0) for s in sessions)

        # Count unique days
        dates = {s['date'][:10] for s in sessions}  # Extract date part
        days_active = len(dates)

        return {
            'total_time_minutes': round(total_seconds / 60, 1),
            'avg_time_per_day': round(total_seconds / 60 / days_active, 1) if days_active > 0 else 0,
            'days_active': days_active,
            'total_chunks': total_chunks
        }

    def get_preferences(self, user_id: str = "default") -> Dict[str, Any]:
        """
        Get user preferences from cache.

        Args:
            user_id: User ID

        Returns:
            Preferences dictionary
        """
        if not isinstance(user_id, str):
            raise ValueError("user_id must be string")

        prefs = self.preferences_cache.get(f"prefs:{user_id}")

        if prefs is None:
            # Default preferences
            prefs = {
                'user_id': user_id,
                'time_budget_minutes': 5,
                'auto_suggest': True,
                'weekly_review_day': 'sunday',
                'weekly_review_time': '10:00',
                'batch_size': 20,
                'default_lifecycle': 'temporary'
            }
            self.preferences_cache.set(f"prefs:{user_id}", prefs)

        return prefs

    def save_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """
        Save user preferences to cache.

        Args:
            user_id: User ID
            preferences: Preferences dictionary
        """
        if not isinstance(user_id, str):
            raise ValueError("user_id must be string")
        if not isinstance(preferences, dict):
            raise ValueError("preferences must be dict")

        # Validate required fields
        required_fields = {
            'time_budget_minutes', 'auto_suggest', 'weekly_review_day',
            'weekly_review_time', 'batch_size', 'default_lifecycle'
        }
        if not required_fields.issubset(preferences.keys()):
            raise ValueError("Missing required fields")

        # Save to cache
        self.preferences_cache.set(f"prefs:{user_id}", preferences)
        logger.info(f"Saved preferences for user {user_id}")

    def auto_suggest_lifecycle(self, chunk: Dict[str, Any]) -> str:
        """
        Auto-suggest lifecycle tag based on heuristics.

        Args:
            chunk: Chunk dictionary with 'text' field

        Returns:
            Suggested lifecycle tag
        """
        if 'text' not in chunk:
            raise ValueError("chunk must have 'text' field")

        text = chunk['text'].lower()
        word_count = len(text.split())

        # Rule 1: TODO/FIXME → temporary
        if 'todo' in text or 'fixme' in text:
            return self.LIFECYCLE_TEMPORARY

        # Rule 2: Reference/Definition → permanent
        if 'reference' in text or 'definition' in text:
            return self.LIFECYCLE_PERMANENT

        # Rule 3: <50 words → ephemeral
        if word_count < 50:
            return self.LIFECYCLE_EPHEMERAL

        # Rule 4: >200 words → permanent
        if word_count > 200:
            return self.LIFECYCLE_PERMANENT

        # Default → temporary
        return self.LIFECYCLE_TEMPORARY
