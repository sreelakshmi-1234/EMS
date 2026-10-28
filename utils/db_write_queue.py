"""Queues consumed by the database writer service."""

import asyncio

DB_WRITE_QUEUE = asyncio.Queue()
VICTORIA_DB_WRITE_QUEUE = asyncio.Queue()
GARBAGE_QUEUE = asyncio.Queue()
