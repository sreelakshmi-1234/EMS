"""Minimal PostgreSQL connection factory for alarm and event storage."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


# Load the repository's local database settings before reading os.environ.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def get_connection():
    """Return a new PostgreSQL connection using environment configuration."""
    return psycopg.connect(
        host=os.getenv("EMS_DB_HOST", "127.0.0.1"),
        port=os.getenv("EMS_DB_PORT", "5432"),
        dbname=os.getenv("EMS_DB_NAME", "ems"),
        user=os.getenv("EMS_DB_USER", "postgres"),
        password=os.getenv("EMS_DB_PASSWORD"),
    )
