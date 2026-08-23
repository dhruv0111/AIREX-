"""Local-dev helper: seed the SQLite database (used only for manual smoke runs)."""

import asyncio

from app.db.session import get_session_factory
from app.seed import run_seed


async def _main() -> None:
    async with get_session_factory()() as session:
        await run_seed(session)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(_main())
    print("SEED_OK")
