"""Audit scan coverage: price data, TA, GEX, dormant signal chain."""
import asyncio, sys
from datetime import date
sys.path.insert(0, 'src')
from eigenview.data.storage import AsyncSessionLocal, FactorScore, Price, Chain, DormantBet
from sqlalchemy import select, func, text

async def audit():
    async with AsyncSessionLocal() as s:
        today = date.today()

        # How many scanned tickers have price data
        scanned = (await s.execute(select(FactorScore.ticker).where(FactorScore.date == today))).scalars().all()
        print(f"Scanned tickers: {len(scanned)}")

        has_price = (await s.execute(
            select(func.count(func.distinct(Price.ticker)))
            .where(Price.ticker.in_(scanned), Price.timeframe == '1d')
        )).scalar()
        print(f"Tickers with price data: {has_price}")

        # Price rows total, date range
        price_range = (await s.execute(
            select(func.min(Price.date), func.max(Price.date), func.count())
            .where(Price.timeframe == '1d')
        )).one()
        print(f"Price table: {price_range[2]} rows, {price_range[0]} to {price_range[1]}")

        # Chain coverage
        chain_tickers = (await s.execute(select(func.count(func.distinct(Chain.ticker))))).scalar()
        chain_rows = (await s.execute(select(func.count()).select_from(Chain))).scalar()
        print(f"Chain tickers: {chain_tickers}, rows: {chain_rows}")

        # TA: how many had real firing patterns (not no_pattern)
        firing = (await s.execute(
            select(func.count()).select_from(FactorScore)
            .where(FactorScore.date == today, FactorScore.ta_label != 'no_pattern')
        )).scalar()
        no_pat = (await s.execute(
            select(func.count()).select_from(FactorScore)
            .where(FactorScore.date == today, FactorScore.ta_label == 'no_pattern')
        )).scalar()
        print(f"TA firing patterns: {firing}, no_pattern: {no_pat}")

        # GEX breakdown
        gex_firing = (await s.execute(
            select(func.count()).select_from(FactorScore)
            .where(FactorScore.date == today, FactorScore.gex_strength > 0)
        )).scalar()
        gex_labels = (await s.execute(
            select(FactorScore.gex_label, func.count())
            .where(FactorScore.date == today)
            .group_by(FactorScore.gex_label).order_by(func.count().desc())
        )).all()
        print(f"GEX firing (strength>0): {gex_firing}")
        for l, c in gex_labels[:8]:
            print(f"  gex_label={l!r}: {c}")

        # Dormant: tickers with firing signal today
        dorm_firing = (await s.execute(
            select(func.count()).select_from(FactorScore)
            .where(FactorScore.date == today, FactorScore.dormant_strength > 0)
        )).scalar()
        print(f"Dormant firing today: {dorm_firing}")

        # factors_firing distribution
        ff_dist = (await s.execute(
            select(FactorScore.factors_firing, func.count())
            .where(FactorScore.date == today)
            .group_by(FactorScore.factors_firing).order_by(FactorScore.factors_firing.desc())
        )).all()
        print("factors_firing distribution:")
        for ff, cnt in ff_dist:
            print(f"  {ff} factors: {cnt} tickers")

asyncio.run(audit())
