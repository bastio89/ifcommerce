"""asyncpg-Connection-Pool.

Das Datenbankschema ist in ``/prisma/schema.prisma`` definiert und wird
ausschließlich über ``prisma migrate`` verwaltet. Das Backend greift auf die
von Prisma erzeugten Tabellen über einen schlanken, asynchronen
Repository-Layer zu – ohne ORM-Overhead im heißen Request-Pfad.
"""

from __future__ import annotations

import asyncpg

from app.config import Settings


async def create_pool(settings: Settings) -> asyncpg.Pool:
    dsn, options = settings.asyncpg_connect_options()
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        # Als Startparameter statt "SET TIME ZONE": übersteht das RESET ALL des Pools
        # bei jeder Rückgabe und wird auch von PgBouncer/Neon-Poolern akzeptiert.
        server_settings={"timezone": "UTC", "application_name": "decidecommerce-backend"},
        command_timeout=10,
        **options,
    )
