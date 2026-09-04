import asyncio
import os
import sys

sys.path.insert(0, r"c:\Users\testing\Desktop\AI_Reliability\apps\api")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///c:/Users/testing/Desktop/AI_Reliability/apps/api/data/airex.db"

from sqlalchemy import select
from app.db.session import get_session_factory
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.models.provider import Provider, Model
from app.models.project import Project

async def check():
    session_factory = get_session_factory()
    async with session_factory() as session:
        users = (await session.scalars(select(User))).all()
        for u in users:
            print(f"User: id={u.id}, email={u.email}")
        members = (await session.scalars(select(OrganizationMember))).all()
        for m in members:
            print(f"Member: user_id={m.user_id}, org_id={m.organization_id}, role={m.role}")
        orgs = (await session.scalars(select(Organization))).all()
        for o in orgs:
            print(f"Org: id={o.id}, name={o.name}")
        provs = (await session.scalars(select(Provider))).all()
        for p in provs:
            print(f"Provider: id={p.id}, name={p.name}, org={p.organization_id}")
        projs = (await session.scalars(select(Project))).all()
        for pr in projs:
            print(f"Project: id={pr.id}, name={pr.name}, org={pr.organization_id}")

if __name__ == "__main__":
    asyncio.run(check())
