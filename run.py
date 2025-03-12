#!/usr/bin/env python
"""
Run script for the Glupper application.

This script serves as the entry point for the application,
handling initialization and startup of services.
"""

import asyncio
import logging
import argparse
from typing import Optional

import uvicorn

from src.core.db import init_db
from src.utils.create_tables import create_database_tables


async def setup_database(create_tables: bool = False) -> None:
    """
    Set up the database connection and optionally create tables.
    
    Args:
        create_tables: Whether to create database tables.
    """
    # Initialize the database connection pool
    await init_db()
    
    # Optionally create tables
    if create_tables:
        await create_database_tables()


def main(host: str = "127.0.0.1", port: int = 8000, reload: bool = True, 
         workers: int = 4, create_tables: bool = False) -> None:
    """
    Main entry point for the application.
    
    Args:
        host: Host to bind the server to.
        port: Port to bind the server to.
        reload: Whether to reload the server on code changes.
        workers: Number of worker processes.
        create_tables: Whether to create database tables.
    """
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Set up the database
    if create_tables:
        asyncio.run(setup_database(create_tables=True))
        logging.info("Database tables created")
    
    # Start the FastAPI application
    logging.info(f"Starting FastAPI application on {host}:{port}")
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Glupper application")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--no-reload", action="store_false", dest="reload", help="Disable auto-reload")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker processes")
    parser.add_argument("--create-tables", action="store_true", help="Create database tables")
    
    args = parser.parse_args()
    main(
        host=args.host, 
        port=args.port, 
        reload=args.reload,
        workers=args.workers,
        create_tables=args.create_tables
    )
