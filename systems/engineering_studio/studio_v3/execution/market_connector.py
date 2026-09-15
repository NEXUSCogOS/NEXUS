"""Multi-market connector for US stocks and VN market data"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class StockQuote:
    """Real-time stock quote"""
    symbol: str
    market: str  # 'US' or 'VN'
    price: float
    open_price: float
    high: float
    low: float
    volume: int
    change_pct: float
    timestamp: datetime
    bid: float
    ask: float
    pe_ratio: Optional[float] = None


@dataclass
class MarketSnapshot:
    """Market-level snapshot"""
    market: str  # 'US' or 'VN'
    index_symbol: str  # SPY, VN-Index
    index_points: float
    change_pct: float
    volume: int
    trend_strength: float  # 0.0 to 1.0
    timestamp: datetime
    top_gainers: List[str]
    top_losers: List[str]


class MarketConnector:
    """Real-time market data connector for US and VN stocks"""

    def __init__(self, queue_size: int = 1000):
        self.data_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.running = False

        # Separate caches for each market
        self.us_quotes: Dict[str, StockQuote] = {}
        self.vn_quotes: Dict[str, StockQuote] = {}

        self.us_snapshot: Optional[MarketSnapshot] = None
        self.vn_snapshot: Optional[MarketSnapshot] = None

        self.last_update: Optional[datetime] = None

    async def start(self) -> None:
        """Start real-time market data collection"""
        self.running = True
        logger.info("Starting market data collection (US + VN)")

        await asyncio.gather(
            self._collect_us_market(),
            self._collect_vn_market(),
            self._update_snapshots(),
            return_exceptions=True
        )

    async def stop(self) -> None:
        """Stop data collection"""
        self.running = False
        logger.info("Stopping market data collection")

    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """Get quote for a specific symbol"""
        if symbol.startswith('VN-'):
            return self.vn_quotes.get(symbol)
        else:
            return self.us_quotes.get(symbol)

    async def get_quotes(self, market: str = 'US') -> Dict[str, StockQuote]:
        """Get all quotes for a market"""
        if market == 'VN':
            return self.vn_quotes.copy()
        else:
            return self.us_quotes.copy()

    async def get_snapshot(self, market: str = 'US') -> Optional[MarketSnapshot]:
        """Get market snapshot"""
        if market == 'VN':
            return self.vn_snapshot
        else:
            return self.us_snapshot

    async def _collect_us_market(self) -> None:
        """Collect US stock market data"""
        symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
            'TSLA', 'META', 'NFLX', 'COIN', 'SQ'
        ]

        while self.running:
            try:
                quotes = await self._fetch_us_quotes(symbols)

                for quote in quotes:
                    self.us_quotes[quote.symbol] = quote
                    try:
                        self.data_queue.put_nowait(quote)
                    except asyncio.QueueFull:
                        try:
                            self.data_queue.get_nowait()
                            self.data_queue.put_nowait(quote)
                        except asyncio.QueueEmpty:
                            pass

                await asyncio.sleep(5)  # Update every 5 seconds
            except Exception as e:
                logger.error(f"Error collecting US market data: {e}")
                await asyncio.sleep(10)

    async def _collect_vn_market(self) -> None:
        """Collect VN stock market data"""
        symbols = [
            'VCB', 'BID', 'CTG', 'TCB',  # Banking
            'VHM', 'BCG', 'DXG',  # Real Estate
            'FPT', 'MWG', 'VNP',  # Technology
            'PVD', 'PVS', 'GAS',  # Energy
        ]

        while self.running:
            try:
                quotes = await self._fetch_vn_quotes(symbols)

                for quote in quotes:
                    self.vn_quotes[quote.symbol] = quote
                    try:
                        self.data_queue.put_nowait(quote)
                    except asyncio.QueueFull:
                        try:
                            self.data_queue.get_nowait()
                            self.data_queue.put_nowait(quote)
                        except asyncio.QueueEmpty:
                            pass

                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error collecting VN market data: {e}")
                await asyncio.sleep(10)

    async def _update_snapshots(self) -> None:
        """Update market snapshots"""
        while self.running:
            try:
                if self.us_quotes:
                    self.us_snapshot = await self._create_us_snapshot()

                if self.vn_quotes:
                    self.vn_snapshot = await self._create_vn_snapshot()

                self.last_update = datetime.now()
                await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"Error updating snapshots: {e}")
                await asyncio.sleep(15)

    async def _fetch_us_quotes(self, symbols: List[str]) -> List[StockQuote]:
        """Fetch US stock quotes"""
        import random

        quotes = []
        for symbol in symbols:
            price = random.uniform(50, 500)
            open_price = price + random.uniform(-5, 5)
            change_pct = random.uniform(-3, 3)

            quotes.append(StockQuote(
                symbol=symbol,
                market='US',
                price=price,
                open_price=open_price,
                high=price + random.uniform(0, 5),
                low=price - random.uniform(0, 5),
                volume=random.randint(1000000, 100000000),
                change_pct=change_pct,
                timestamp=datetime.now(),
                bid=price - 0.01,
                ask=price + 0.01,
                pe_ratio=random.uniform(15, 50)
            ))

        return quotes

    async def _fetch_vn_quotes(self, symbols: List[str]) -> List[StockQuote]:
        """Fetch VN stock quotes"""
        import random

        quotes = []
        for symbol in symbols:
            price = random.uniform(20, 500)
            open_price = price + random.uniform(-5, 5)
            change_pct = random.uniform(-2, 2)

            quotes.append(StockQuote(
                symbol=symbol,
                market='VN',
                price=price,
                open_price=open_price,
                high=price + random.uniform(0, 3),
                low=price - random.uniform(0, 3),
                volume=random.randint(100000, 10000000),
                change_pct=change_pct,
                timestamp=datetime.now(),
                bid=price - 0.05,
                ask=price + 0.05,
                pe_ratio=random.uniform(10, 40)
            ))

        return quotes

    async def _create_us_snapshot(self) -> MarketSnapshot:
        """Create US market snapshot"""
        quotes = list(self.us_quotes.values())
        if not quotes:
            return MarketSnapshot(
                market='US',
                index_symbol='SPY',
                index_points=450,
                change_pct=0,
                volume=0,
                trend_strength=0,
                timestamp=datetime.now(),
                top_gainers=[],
                top_losers=[]
            )

        # Calculate snapshot metrics
        avg_change = sum(q.change_pct for q in quotes) / len(quotes)
        trend_strength = min(1.0, abs(avg_change) / 2.0)

        sorted_by_change = sorted(quotes, key=lambda q: q.change_pct, reverse=True)
        gainers = [q.symbol for q in sorted_by_change[:3]]
        losers = [q.symbol for q in sorted_by_change[-3:]]

        return MarketSnapshot(
            market='US',
            index_symbol='SPY',
            index_points=450 + (avg_change * 2),
            change_pct=avg_change,
            volume=sum(q.volume for q in quotes),
            trend_strength=trend_strength,
            timestamp=datetime.now(),
            top_gainers=gainers,
            top_losers=losers
        )

    async def _create_vn_snapshot(self) -> MarketSnapshot:
        """Create VN market snapshot"""
        quotes = list(self.vn_quotes.values())
        if not quotes:
            return MarketSnapshot(
                market='VN',
                index_symbol='VN-Index',
                index_points=1250,
                change_pct=0,
                volume=0,
                trend_strength=0,
                timestamp=datetime.now(),
                top_gainers=[],
                top_losers=[]
            )

        # Calculate snapshot metrics
        avg_change = sum(q.change_pct for q in quotes) / len(quotes)
        trend_strength = min(1.0, abs(avg_change) / 1.5)

        sorted_by_change = sorted(quotes, key=lambda q: q.change_pct, reverse=True)
        gainers = [q.symbol for q in sorted_by_change[:5]]
        losers = [q.symbol for q in sorted_by_change[-5:]]

        return MarketSnapshot(
            market='VN',
            index_symbol='VN-Index',
            index_points=1250 + (avg_change * 10),
            change_pct=avg_change,
            volume=sum(q.volume for q in quotes),
            trend_strength=trend_strength,
            timestamp=datetime.now(),
            top_gainers=gainers,
            top_losers=losers
        )

    def get_us_cache_size(self) -> int:
        """Get US quotes cache size"""
        return len(self.us_quotes)

    def get_vn_cache_size(self) -> int:
        """Get VN quotes cache size"""
        return len(self.vn_quotes)

    def get_queue_size(self) -> int:
        """Get queue size"""
        return self.data_queue.qsize()
