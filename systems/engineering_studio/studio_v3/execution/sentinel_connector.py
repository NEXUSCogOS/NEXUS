"""Real-time trend data connector for Sentinel ELITE system"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrendData:
    """Real-time trend data point"""
    symbol: str
    price: float
    volume: int
    change_pct: float
    timestamp: datetime
    sector: str
    is_trending: bool
    momentum: float  # -1.0 to 1.0


@dataclass
class MarketTrend:
    """Market-level trend information"""
    index_name: str
    points: float
    change_pct: float
    trend_strength: float  # 0.0 to 1.0
    trending_symbols: List[str]
    timestamp: datetime


class SentinelConnector:
    """Connect to Sentinel data sources for real-time trend analysis"""

    def __init__(self, queue_size: int = 1000):
        self.data_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.running = False
        self.trends_cache: Dict[str, TrendData] = {}
        self.market_trends: List[MarketTrend] = []
        self.last_update: Optional[datetime] = None

    async def start(self) -> None:
        """Start real-time data collection"""
        self.running = True
        logger.info("Starting Sentinel real-time data collection")

        # Run data collection concurrently
        await asyncio.gather(
            self._collect_vn_market_trends(),
            self._collect_sector_trends(),
            self._update_momentum_indicators(),
            return_exceptions=True
        )

    async def stop(self) -> None:
        """Stop data collection"""
        self.running = False
        logger.info("Stopping Sentinel data collection")

    async def get_data(self, symbol: Optional[str] = None, timeout: float = 1.0) -> Optional[TrendData]:
        """Get trend data non-blocking"""
        try:
            if symbol:
                return self.trends_cache.get(symbol)

            # Return next item from queue
            return await asyncio.wait_for(self.data_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def get_market_trends(self) -> List[MarketTrend]:
        """Get current market-level trends"""
        return self.market_trends

    async def _collect_vn_market_trends(self) -> None:
        """Collect VN market trends (VN-Index, VN30, etc.)"""
        while self.running:
            try:
                # Simulate real-time VN market data
                # In production: use vnstock or TCBS API
                trends = await self._fetch_vn_indices()

                for trend in trends:
                    self.market_trends.append(trend)
                    if len(self.market_trends) > 100:
                        self.market_trends.pop(0)

                await asyncio.sleep(5)  # Update every 5 seconds
            except Exception as e:
                logger.error(f"Error collecting VN trends: {e}")
                await asyncio.sleep(10)

    async def _collect_sector_trends(self) -> None:
        """Collect sector-level trends"""
        sectors = ['Banking', 'Real Estate', 'Technology', 'Energy', 'Retail']

        while self.running:
            try:
                for sector in sectors:
                    trends = await self._fetch_sector_data(sector)

                    for trend_data in trends:
                        self.trends_cache[trend_data.symbol] = trend_data
                        try:
                            self.data_queue.put_nowait(trend_data)
                        except asyncio.QueueFull:
                            # Drop oldest if queue full
                            try:
                                self.data_queue.get_nowait()
                                self.data_queue.put_nowait(trend_data)
                            except asyncio.QueueEmpty:
                                pass

                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Error collecting sector trends: {e}")
                await asyncio.sleep(10)

    async def _update_momentum_indicators(self) -> None:
        """Update momentum indicators for all tracked symbols"""
        while self.running:
            try:
                for symbol, trend_data in self.trends_cache.items():
                    # Calculate momentum: -1.0 (sell) to 1.0 (buy)
                    momentum = await self._calculate_momentum(symbol, trend_data)

                    updated = TrendData(
                        symbol=trend_data.symbol,
                        price=trend_data.price,
                        volume=trend_data.volume,
                        change_pct=trend_data.change_pct,
                        timestamp=datetime.now(),
                        sector=trend_data.sector,
                        is_trending=abs(momentum) > 0.5,
                        momentum=momentum
                    )
                    self.trends_cache[symbol] = updated

                self.last_update = datetime.now()
                await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"Error updating momentum: {e}")
                await asyncio.sleep(15)

    async def _fetch_vn_indices(self) -> List[MarketTrend]:
        """Fetch VN-Index, VN30, VNMID data"""
        indices = [
            ('VN-Index', 1250.5, 0.85),
            ('VN30', 950.25, 1.2),
            ('VNMID', 520.75, 0.45),
        ]

        trends = []
        for index_name, points, change_pct in indices:
            trend_strength = min(1.0, abs(change_pct) / 2.0)

            trends.append(MarketTrend(
                index_name=index_name,
                points=points,
                change_pct=change_pct,
                trend_strength=trend_strength,
                trending_symbols=await self._get_trending_symbols(),
                timestamp=datetime.now()
            ))

        return trends

    async def _fetch_sector_data(self, sector: str) -> List[TrendData]:
        """Fetch sector-specific trend data"""
        # Simulate sector data
        symbols_by_sector = {
            'Banking': ['VCB', 'BID', 'CTG', 'TCB'],
            'Real Estate': ['VHM', 'BCG', 'DXG'],
            'Technology': ['FPT', 'MWG', 'VNP'],
            'Energy': ['PVD', 'PVS', 'GAS'],
            'Retail': ['MWG', 'DTK', 'PNJ'],
        }

        symbols = symbols_by_sector.get(sector, [])
        trends = []

        for symbol in symbols:
            # Simulate realistic trend data
            import random
            price = 100 + random.uniform(-20, 20)
            volume = random.randint(100000, 10000000)
            change_pct = random.uniform(-5, 5)

            trends.append(TrendData(
                symbol=symbol,
                price=price,
                volume=volume,
                change_pct=change_pct,
                timestamp=datetime.now(),
                sector=sector,
                is_trending=abs(change_pct) > 2.0,
                momentum=change_pct / 5.0  # Convert to -1.0 to 1.0
            ))

        return trends

    async def _calculate_momentum(self, symbol: str, trend_data: TrendData) -> float:
        """Calculate momentum indicator for symbol"""
        # Simple momentum: change_pct normalized to -1.0 to 1.0
        base_momentum = trend_data.change_pct / 5.0
        return min(1.0, max(-1.0, base_momentum))

    async def _get_trending_symbols(self) -> List[str]:
        """Get list of currently trending symbols"""
        trending = []
        for symbol, trend_data in self.trends_cache.items():
            if trend_data.is_trending and abs(trend_data.momentum) > 0.6:
                trending.append(symbol)

        return trending[:10]  # Top 10 trending

    def get_cache_size(self) -> int:
        """Get current cache size"""
        return len(self.trends_cache)

    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.data_queue.qsize()
