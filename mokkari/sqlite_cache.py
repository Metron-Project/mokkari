"""SQLite Cache module.

This module provides the following classes:

- SqliteCache
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from typing_extensions import Self

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


class SqliteCache:
    """A thread-safe class for caching data using SQLite.

    This cache implementation provides:
    - Automatic expiration of cached data
    - Thread-safe operations using context managers
    - Proper error handling and logging
    - Database connection management
    - Cleanup of expired entries

    Args:
        db_name: Path to the SQLite database file
        expire_days: Number of days after which cache entries expire (None = no expiration)
        cleanup_on_init: Whether to clean up expired entries on initialization
    """

    def __init__(
        self,
        db_name: str | Path = "mokkari_cache.db",
        expire_days: int | None = None,
        cleanup_on_init: bool = True,
    ) -> None:
        """Initialize a new SqliteCache instance."""
        self.db_path = Path(db_name)
        self.expire_days = expire_days

        # Ensure the database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize the database
        self._init_database()

        if cleanup_on_init:
            self.cleanup()

        logger.info(
            "SqliteCache initialized: db=%s, expire_days=%s", self.db_path, self.expire_days
        )

    def _init_database(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    key TEXT PRIMARY KEY,
                    json TEXT NOT NULL,
                    expire TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for faster expiration queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_responses_expire
                ON responses(expire)
            """)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,  # 30 second timeout
                isolation_level=None,  # Autocommit mode
            )
            conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Better performance
            yield conn
        except sqlite3.Error:
            logger.exception("Database error")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def get(self, key: str) -> Any | None:
        """Retrieve data from the cache database.

        Args:
            key: The cache key to look up

        Returns:
            The cached data if found and not expired, None otherwise

        Raises:
            sqlite3.Error: If there's a database error
            json.JSONDecodeError: If the cached data is corrupted
        """
        if not key:
            return None

        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT json, expire FROM responses WHERE key = ?", (key,))
                result = cursor.fetchone()

                if not result:
                    logger.debug("Cache miss for key: %s", key)
                    return None

                json_data, expire_str = result

                # Check if the entry has expired
                if self._is_expired(expire_str):
                    logger.debug("Cache entry expired for key: %s", key)
                    self._delete_key(key)
                    return None

                logger.debug("Cache hit for key: %s", key)
                return json.loads(json_data)

        except json.JSONDecodeError:
            logger.exception("Failed to decode cached JSON for key %s", key)
            # Remove corrupted entry
            self._delete_key(key)
            return None
        except sqlite3.Error:
            logger.exception("Database error retrieving key %s", key)
            return None

    def store(self, key: str, value: Any) -> bool:
        """Save data to the cache database.

        Args:
            key: The cache key
            value: The data to cache (must be JSON serializable)

        Returns:
            True if stored successfully, False otherwise

        Raises:
            sqlite3.Error: If there's a database error
        """
        if not key:
            logger.warning("Attempted to store with empty key")
            return False

        try:
            json_data = json.dumps(value, separators=(",", ":"))  # Compact JSON
            expire_str = self._calculate_expiration()

            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO responses(key, json, expire)
                       VALUES(?, ?, ?)""",
                    (key, json_data, expire_str),
                )

            logger.debug("Stored cache entry for key: %s", key)
        except TypeError:
            logger.exception("Failed to serialize value for key %s", key)
            return False
        except sqlite3.Error:
            logger.exception("Database error storing key %s", key)
            return False
        else:
            return True

    def delete(self, key: str) -> bool:
        """Delete a specific cache entry.

        Args:
            key: The cache key to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        return self._delete_key(key)

    def _delete_key(self, key: str) -> bool:
        """Internal method to delete a cache key."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM responses WHERE key = ?", (key,))
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.debug("Deleted cache entry for key: %s", key)
                return deleted
        except sqlite3.Error:
            logger.exception("Database error deleting key %s", key)
            return False

    def cleanup(self) -> int:
        """Remove expired data from the cache database.

        Returns:
            Number of entries removed
        """
        if not self.expire_days:
            logger.debug("No expiration configured, skipping cleanup")
            return 0

        try:
            current_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM responses WHERE expire < ?", (current_date,))
                deleted_count = cursor.rowcount

            if deleted_count > 0:
                logger.info("Cleaned up %d expired cache entries", deleted_count)
            else:
                logger.debug("No expired cache entries to clean up")
        except sqlite3.Error:
            logger.exception("Database error during cleanup")
            return 0
        else:
            return deleted_count

    def clear(self) -> bool:
        """Clear all cache entries.

        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM responses")
                deleted_count = cursor.rowcount

            logger.info("Cleared %d cache entries", deleted_count)
        except sqlite3.Error:
            logger.exception("Database error during clear")
            return False
        else:
            return True

    def size(self) -> int:
        """Get the number of cache entries.

        Returns:
            Number of entries in the cache
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM responses")
                return cursor.fetchone()[0]
        except sqlite3.Error:
            logger.exception("Database error getting cache size")
            return 0

    def _is_expired(self, expire_str: str) -> bool:
        """Check if a cache entry has expired."""
        if not self.expire_days:
            return False

        try:
            expire_date = datetime.strptime(expire_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            current_date = datetime.now(tz=timezone.utc)
        except ValueError:
            logger.warning("Invalid expire date format: %s", expire_str)
            return True  # Treat invalid dates as expired
        else:
            return current_date >= expire_date

    def _calculate_expiration(self) -> str:
        """Calculate the expiration date string for cache data."""
        if self.expire_days:
            expire_date = datetime.now(tz=timezone.utc) + timedelta(days=self.expire_days)
        else:
            # If no expiration is set, use a far future date
            expire_date = datetime.now(tz=timezone.utc) + timedelta(days=365 * 100)

        return expire_date.strftime("%Y-%m-%d")

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with cleanup."""
        self.cleanup()

    def __repr__(self) -> str:
        """String representation of the cache."""
        return f"SqliteCache(db_path={self.db_path}, expire_days={self.expire_days}, size={self.size()})"
