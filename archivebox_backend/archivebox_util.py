"""
Utilities for interacting with ArchiveBox.
"""

import json
import logging
import os
import subprocess
from typing import Optional

import httpx
from config import ARCHIVEBOX_API_ENDPOINT, ARCHIVEBOX_DATA_DIR

logger = logging.getLogger("archivebox_util")


def archive_url_api(url: str) -> Optional[dict]:
    """
    Archive a URL using the ArchiveBox API
    Returns the ArchiveBox response if successful, None otherwise
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            headers = {"Content-Type": "application/json"}
            payload = {"url": url}

            response = client.post(ARCHIVEBOX_API_ENDPOINT, json=payload, headers=headers)

            if response.status_code in (200, 201):
                return response.json()

            logger.error(f"Failed to archive URL {url}: {response.status_code} {response.text}")
            return None
    except Exception:
        logger.exception(f"Error archiving URL {url}")
        return None


def archive_url_cli(url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Archive a URL using the ArchiveBox CLI
    This can be more reliable in some cases than the API
    Returns the snapshot ID if successful, None otherwise
    """
    try:
        cmd = ["archivebox", "add", url]
        if title:
            cmd.extend(["--title", title])

        # Set working directory to ArchiveBox data dir
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=ARCHIVEBOX_DATA_DIR,
            check=False,
        )

        if result.returncode != 0:
            logger.error(f"Failed to archive URL {url}: {result.stderr}")
            return None

        # Parse output to get snapshot ID
        for line in result.stdout.splitlines():
            if "Saved:" in line and "index.html" in line:
                # Example format: "[√] Saved: archive/1234567890/index.html"
                parts = line.split("/")
                if len(parts) >= 2:
                    return parts[-2]
        
        logger.warning(f"Archived URL but couldn't extract snapshot ID: {result.stdout}")
        return None
    except Exception:
        logger.exception("Error archiving URL with CLI")
        return None


def get_snapshot_files(snapshot_id: str) -> list[dict]:
    """
    Get information about files in a snapshot
    Returns a list of file info dictionaries
    """
    try:
        snapshot_dir = os.path.join(ARCHIVEBOX_DATA_DIR, "archive", snapshot_id)
        if not os.path.exists(snapshot_dir):
            logger.error(f"Snapshot directory not found: {snapshot_dir}")
            return []

        # Read the JSON index file if available
        index_path = os.path.join(snapshot_dir, "index.json")
        if os.path.exists(index_path):
            with open(index_path) as f:
                index_data = json.load(f)

            # Extract files from the snapshot index
            files = []
            for archive_method, output in index_data.get("archives", {}).items():
                if output.get("status") == "succeeded" and "output" in output:
                    output_path = output["output"]
                    files.append(
                        {
                            "path": os.path.join(snapshot_dir, output_path),
                            "filename": os.path.basename(output_path),
                            "method": archive_method,
                            "content_type": get_content_type(output_path),
                        },
                    )
            return files

        # Fallback: List all files in the directory
        return [
            {
                "path": os.path.join(snapshot_dir, filename),
                "filename": filename,
                "method": "unknown",
                "content_type": get_content_type(filename),
            }
            for filename in os.listdir(snapshot_dir)
            if os.path.isfile(os.path.join(snapshot_dir, filename))
        ]
    except Exception:
        logger.exception("Error getting snapshot files")
        return []


def get_content_type(filename: str) -> str:
    """Determine content type based on filename"""
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        ".html": "text/html",
        ".htm": "text/html",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".json": "application/json",
        ".txt": "text/plain",
        ".css": "text/css",
        ".js": "application/javascript",
        ".xml": "application/xml",
        ".zip": "application/zip",
    }
    return content_types.get(ext, "application/octet-stream")
