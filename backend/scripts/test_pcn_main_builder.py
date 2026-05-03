import asyncio
from datetime import datetime
import sys
sys.path.insert(0, r"d:\alarm\SVOD_SOFT\backend")

from app.db.session import SessionLocal
from app.api.v1.reports_pcn_main import build_pcn_main_report_xlsx

async def main():
    async with SessionLocal() as session:
        data, cnt = await build_pcn_main_report_xlsx(
            session,
            date_from=datetime(2026, 5, 1, 0, 0),
            date_to=datetime(2026, 5, 2, 23, 59),
        )
        print('count=', cnt, 'bytes=', len(data))

asyncio.run(main())
