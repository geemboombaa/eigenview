import asyncio, sys
sys.path.insert(0, 'src')
from eigenview.data.storage import AsyncSessionLocal, FactorScore, Pick, DormantBet
from sqlalchemy import select, func, text

async def check():
    async with AsyncSessionLocal() as s:
        fs_count = (await s.execute(select(func.count()).select_from(FactorScore))).scalar()
        fs_dates = (await s.execute(select(func.count(func.distinct(FactorScore.date))).select_from(FactorScore))).scalar()
        fs_today = (await s.execute(select(func.count()).select_from(FactorScore).where(FactorScore.date == __import__('datetime').date.today()))).scalar()
        pick_count = (await s.execute(select(func.count()).select_from(Pick))).scalar()
        db_count = (await s.execute(select(func.count()).select_from(DormantBet))).scalar()

        ta_labels = (await s.execute(
            select(FactorScore.ta_label, func.count()).select_from(FactorScore)
            .where(FactorScore.date == __import__('datetime').date.today())
            .group_by(FactorScore.ta_label).order_by(func.count().desc()).limit(15)
        )).all()

        ta_firing = (await s.execute(
            select(FactorScore.ticker, FactorScore.ta_label, FactorScore.ta_strength)
            .where(FactorScore.date == __import__('datetime').date.today(), FactorScore.ta_strength > 0)
            .order_by(FactorScore.ta_strength.desc()).limit(20)
        )).all()

        # Check for null/none ta_labels (no data tickers)
        null_ta = (await s.execute(
            select(func.count()).select_from(FactorScore)
            .where(FactorScore.date == __import__('datetime').date.today(), FactorScore.ta_label == None)
        )).scalar()

        print(f"FactorScore: {fs_count} total, {fs_dates} dates, {fs_today} today")
        print(f"Picks total: {pick_count}")
        print(f"DormantBets: {db_count}")
        print(f"TA null label today: {null_ta}")
        print()
        print("TA labels today:")
        for label, cnt in ta_labels:
            print(f"  {label!r}: {cnt}")
        print()
        print("Top TA firing today (strength>0):")
        for tk, label, st in ta_firing:
            print(f"  {tk}: {label} ({st:.2f})")

asyncio.run(check())
