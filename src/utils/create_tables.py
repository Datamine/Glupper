"""
Utility script to create database tables from models.

This script provides a function to create all necessary database tables
based on the models defined in the application.
"""

import asyncio
import logging
from typing import Optional

import asyncpg

from src.config_secrets import DATABASE_URL
from src.models.models import User, Post, Like, Follow, Mute, Message, Timeline


async def create_database_tables(connection_string: Optional[str] = None) -> None:
    """
    Create all database tables based on the models.

    This function connects to the database and creates tables for all model
    classes defined in src/models/models.py. It ensures tables have the proper
    columns, constraints, and indexes.

    Args:
        connection_string: Database connection string. If not provided,
            uses the DATABASE_URL from config_secrets.py.
    """
    conn_string = connection_string or DATABASE_URL
    
    logging.info("Connecting to database...")
    conn = await asyncpg.connect(conn_string)
    
    try:
        logging.info("Creating tables...")
        
        # Users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                bio TEXT,
                profile_picture_url TEXT,
                follower_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """)
        logging.info("Created users table")

        # Posts table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                media_urls TEXT[] DEFAULT '{}',
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                repost_count INTEGER DEFAULT 0,
                is_repost BOOLEAN DEFAULT FALSE,
                original_post_id UUID REFERENCES posts(id),
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id);
            CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC);
        """)
        logging.info("Created posts table")

        # Likes table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(user_id, post_id)
            );
            CREATE INDEX IF NOT EXISTS idx_likes_post_id ON likes(post_id);
            CREATE INDEX IF NOT EXISTS idx_likes_user_id ON likes(user_id);
        """)
        logging.info("Created likes table")

        # Follows table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS follows (
                id UUID PRIMARY KEY,
                follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                followee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(follower_id, followee_id)
            );
            CREATE INDEX IF NOT EXISTS idx_follows_follower_id ON follows(follower_id);
            CREATE INDEX IF NOT EXISTS idx_follows_followee_id ON follows(followee_id);
        """)
        logging.info("Created follows table")

        # Mutes table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mutes (
                id UUID PRIMARY KEY,
                muter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                muted_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(muter_id, muted_id)
            );
            CREATE INDEX IF NOT EXISTS idx_mutes_muter_id ON mutes(muter_id);
            CREATE INDEX IF NOT EXISTS idx_mutes_muted_id ON mutes(muted_id);
        """)
        logging.info("Created mutes table")

        # Messages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY,
                sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                recipient_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);
            CREATE INDEX IF NOT EXISTS idx_messages_recipient_id ON messages(recipient_id);
            CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(
                LEAST(sender_id, recipient_id),
                GREATEST(sender_id, recipient_id)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);
        """)
        logging.info("Created messages table")

        # Archived URLs table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS archived_urls (
                id SERIAL PRIMARY KEY,
                post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                original_url TEXT NOT NULL,
                archived_url TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                UNIQUE(post_id, original_url)
            );
            CREATE INDEX IF NOT EXISTS idx_archived_urls_post_id ON archived_urls(post_id);
            CREATE INDEX IF NOT EXISTS idx_archived_urls_original_url ON archived_urls(original_url);
        """)
        logging.info("Created archived_urls table")
        
        logging.info("All tables created successfully")
    finally:
        await conn.close()
        logging.info("Database connection closed")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(create_database_tables())