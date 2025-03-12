"""
Utilities for working with the Glupper database.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL

logger = logging.getLogger("db_util")


def connect_to_db():
    """
    Connect to the PostgreSQL database
    
    Returns:
        Database connection object if successful, None otherwise
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None


def get_archive_job(conn, job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get information about an archive job
    
    Args:
        conn: Database connection
        job_id: The archive job ID
        
    Returns:
        Dictionary with job information if found, None otherwise
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT 
                    id, post_id, original_url, status, 
                    archived_url, s3_location, archived_key,
                    archive_timestamp, created_at, updated_at
                FROM archived_urls
                WHERE archive_job_id = %s
                """,
                (job_id,),
            )
            result = cur.fetchone()
            return dict(result) if result else None
    except Exception as e:
        logger.error(f"Error getting archive job: {e}")
        return None


def get_pending_jobs(conn, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get a list of pending archive jobs
    
    Args:
        conn: Database connection
        limit: Maximum number of jobs to retrieve
        
    Returns:
        List of job dictionaries
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT 
                    id, post_id, original_url, archive_job_id, 
                    created_at, updated_at
                FROM archived_urls
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (limit,),
            )
            results = cur.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Error getting pending jobs: {e}")
        return []


def update_archive_status(
    conn, 
    job_id: str, 
    status: str, 
    archived_url: Optional[str] = None,
    s3_location: Optional[str] = None,
    archived_key: Optional[str] = None,
) -> bool:
    """
    Update the status of an archive job
    
    Args:
        conn: Database connection
        job_id: The archive job ID
        status: New status (pending, processing, completed, failed)
        archived_url: Optional ArchiveBox URL
        s3_location: Optional S3 location
        archived_key: Optional ArchiveBox key
        
    Returns:
        True if successful, False otherwise
    """
    try:
        now = datetime.now()
        
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE archived_urls
                SET 
                    status = %s, 
                    archived_url = COALESCE(%s, archived_url),
                    s3_location = COALESCE(%s, s3_location),
                    archived_key = COALESCE(%s, archived_key),
                    archive_timestamp = CASE WHEN %s = 'completed' THEN %s ELSE archive_timestamp END,
                    updated_at = %s
                WHERE archive_job_id = %s
                RETURNING id
                """,
                (status, archived_url, s3_location, archived_key, status, now, now, job_id),
            )
            result = cur.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating archive status: {e}")
        return False