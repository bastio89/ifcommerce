"""asyncpg-Connection-Pool.

Das Datenbankschema ist in ``/prisma/schema.prisma`` definiert und wird
ausschließlich über ``prisma migrate`` verwaltet. Das Backend greift auf die
von Prisma erzeugten Tabellen über einen schlanken, asynchronen
Repository-Layer zu – ohne ORM-Overhead im heißen Request-Pfad.
"""

from __future__ import annotations

import asyncpg

from app.config import Settings


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Alle Zeitstempel sind timestamptz; UTC als Sitzungszeitzone hält
    # Monatsgrenzen (Free-Tier-Kontingent) eindeutig.
    await conn.execute("SET TIME ZONE 'UTC'")


async def create_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=settings.asyncpg_dsn,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        init=_init_connection,
        command_timeout=10,
    )
