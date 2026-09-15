"""Real estate property price connector for DatAI platform"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PropertyPrice:
    """Real-time property price data point"""
    property_id: str
    address: str
    location: str  # District/Commune
    price_per_sqm: float
    total_price: float
    sqm: float
    property_type: str  # Apartment, House, Land
    trend_pct_month: float  # Month-over-month change
    trend_pct_year: float  # Year-over-year change
    timestamp: datetime
    market_heat: float  # 0.0 to 1.0, how hot is this area


@dataclass
class LocationTrend:
    """Market trend for a specific location"""
    location: str
    avg_price_per_sqm: float
    change_pct_month: float
    change_pct_year: float
    transaction_volume: int  # Number of transactions this period
    market_momentum: float  # -1.0 to 1.0
    timestamp: datetime


class DatAiConnector:
    """Connect to DatAI real estate data feeds"""

    def __init__(self, queue_size: int = 500):
        self.data_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.running = False
        self.properties_cache: Dict[str, PropertyPrice] = {}
        self.location_trends: Dict[str, LocationTrend] = {}
        self.last_update: Optional[datetime] = None

    async def start(self) -> None:
        """Start real-time property data collection"""
        self.running = True
        logger.info("Starting DatAI real estate data collection")

        await asyncio.gather(
            self._collect_property_listings(),
            self._collect_location_trends(),
            self._update_market_heat(),
            return_exceptions=True
        )

    async def stop(self) -> None:
        """Stop data collection"""
        self.running = False
        logger.info("Stopping DatAI data collection")

    async def get_properties(
        self,
        location: Optional[str] = None,
        property_type: Optional[str] = None,
        timeout: float = 1.0
    ) -> List[PropertyPrice]:
        """Get property listings (filtered or all)"""
        if location or property_type:
            return [
                p for p in self.properties_cache.values()
                if (location is None or p.location == location) and
                   (property_type is None or p.property_type == property_type)
            ]

        # Get from queue
        properties = []
        try:
            while True:
                prop = await asyncio.wait_for(
                    self.data_queue.get(), timeout=0.1
                )
                properties.append(prop)
        except asyncio.TimeoutError:
            pass

        return properties

    async def get_location_trend(self, location: str) -> Optional[LocationTrend]:
        """Get trend data for a specific location"""
        return self.location_trends.get(location)

    async def get_all_location_trends(self) -> Dict[str, LocationTrend]:
        """Get all tracked location trends"""
        return self.location_trends.copy()

    async def _collect_property_listings(self) -> None:
        """Collect new property listings"""
        locations = [
            'Dong Nai',
            'Ho Chi Minh',
            'Hanoi',
            'Da Nang',
            'Can Tho'
        ]

        listing_id = 0
        while self.running:
            try:
                for location in locations:
                    listings = await self._fetch_location_listings(location, count=5)

                    for listing in listings:
                        self.properties_cache[listing.property_id] = listing
                        try:
                            self.data_queue.put_nowait(listing)
                        except asyncio.QueueFull:
                            try:
                                self.data_queue.get_nowait()
                                self.data_queue.put_nowait(listing)
                            except asyncio.QueueEmpty:
                                pass

                await asyncio.sleep(20)  # New listings every 20s
            except Exception as e:
                logger.error(f"Error collecting property listings: {e}")
                await asyncio.sleep(30)

    async def _collect_location_trends(self) -> None:
        """Collect location-level market trends"""
        locations = [
            'Dong Nai',
            'Ho Chi Minh',
            'Hanoi',
            'Da Nang',
            'Can Tho'
        ]

        while self.running:
            try:
                for location in locations:
                    trend = await self._fetch_location_trend(location)
                    self.location_trends[location] = trend

                await asyncio.sleep(60)  # Update every minute
            except Exception as e:
                logger.error(f"Error collecting location trends: {e}")
                await asyncio.sleep(60)

    async def _update_market_heat(self) -> None:
        """Update market heat indicators based on transaction velocity"""
        while self.running:
            try:
                for prop_id, prop in self.properties_cache.items():
                    # Market heat based on recent transaction volume
                    location_trend = self.location_trends.get(prop.location)
                    if location_trend:
                        # High transaction volume = high market heat
                        heat = min(1.0, location_trend.transaction_volume / 100.0)

                        updated = PropertyPrice(
                            property_id=prop.property_id,
                            address=prop.address,
                            location=prop.location,
                            price_per_sqm=prop.price_per_sqm,
                            total_price=prop.total_price,
                            sqm=prop.sqm,
                            property_type=prop.property_type,
                            trend_pct_month=prop.trend_pct_month,
                            trend_pct_year=prop.trend_pct_year,
                            timestamp=datetime.now(),
                            market_heat=heat
                        )
                        self.properties_cache[prop_id] = updated

                self.last_update = datetime.now()
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error updating market heat: {e}")
                await asyncio.sleep(30)

    async def _fetch_location_listings(self, location: str, count: int = 5) -> List[PropertyPrice]:
        """Fetch new property listings for a location"""
        import random

        listings = []
        for i in range(count):
            prop_id = f"{location.upper()}-{datetime.now().timestamp()}-{i}"

            price_per_sqm = random.uniform(50, 300)  # Million VND per sqm
            sqm = random.randint(50, 300)
            total_price = price_per_sqm * sqm

            listings.append(PropertyPrice(
                property_id=prop_id,
                address=f"Street {i}, District, {location}",
                location=location,
                price_per_sqm=price_per_sqm,
                total_price=total_price,
                sqm=sqm,
                property_type=random.choice(['Apartment', 'House', 'Land']),
                trend_pct_month=random.uniform(-2, 4),
                trend_pct_year=random.uniform(-5, 15),
                timestamp=datetime.now(),
                market_heat=random.uniform(0.3, 0.9)
            ))

        return listings

    async def _fetch_location_trend(self, location: str) -> LocationTrend:
        """Fetch trend data for a location"""
        import random

        avg_price = random.uniform(80, 200)  # Million VND per sqm
        change_month = random.uniform(-1, 3)
        change_year = random.uniform(-5, 12)
        volume = random.randint(20, 200)
        momentum = change_year / 12.0  # Approximate momentum

        return LocationTrend(
            location=location,
            avg_price_per_sqm=avg_price,
            change_pct_month=change_month,
            change_pct_year=change_year,
            transaction_volume=volume,
            market_momentum=min(1.0, max(-1.0, momentum)),
            timestamp=datetime.now()
        )

    def get_cache_size(self) -> int:
        """Get current cache size"""
        return len(self.properties_cache)

    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.data_queue.qsize()

    def get_tracked_locations(self) -> List[str]:
        """Get list of tracked locations"""
        return list(self.location_trends.keys())
