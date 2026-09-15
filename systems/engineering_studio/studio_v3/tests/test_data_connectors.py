"""Tests for real-time data connectors (TRACK 4)"""
import asyncio
import pytest
from datetime import datetime
from systems.engineering_studio.studio_v3.execution import (
    SentinelConnector,
    DatAiConnector,
    MarketConnector,
    TrendData,
    PropertyPrice,
    StockQuote
)


class TestSentinelConnector:
    """Test Sentinel real-time trend data connector"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test connector initializes properly"""
        connector = SentinelConnector(queue_size=100)
        assert connector.running is False
        assert connector.get_cache_size() == 0
        assert connector.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping data collection"""
        connector = SentinelConnector()

        # Start collection
        start_task = asyncio.create_task(connector.start())
        await asyncio.sleep(0.5)  # Let it run briefly

        # Verify running
        assert connector.running is True

        # Stop collection
        await connector.stop()
        await asyncio.sleep(0.2)

        assert connector.running is False
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_market_trends_collection(self):
        """Test market trends are collected"""
        connector = SentinelConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(3)  # Let it collect

        market_trends = await connector.get_market_trends()
        assert len(market_trends) > 0

        for trend in market_trends:
            assert trend.index_name in ['VN-Index', 'VN30', 'VNMID']
            assert isinstance(trend.points, float)
            assert isinstance(trend.change_pct, float)
            assert 0 <= trend.trend_strength <= 1.0

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_sector_trends_collection(self):
        """Test sector-level trends"""
        connector = SentinelConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(4)  # Let it collect

        assert connector.get_cache_size() > 0

        for symbol, trend in connector.trends_cache.items():
            assert isinstance(trend, TrendData)
            assert trend.symbol == symbol
            assert isinstance(trend.price, float)
            assert isinstance(trend.momentum, float)
            assert -1.0 <= trend.momentum <= 1.0

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_get_data_non_blocking(self):
        """Test non-blocking data retrieval"""
        connector = SentinelConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(2)

        # Get data should not block
        data = await connector.get_data(timeout=0.5)
        # May or may not have data depending on timing

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_queue_overflow_handling(self):
        """Test queue handles overflow gracefully"""
        connector = SentinelConnector(queue_size=5)
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(3)

        # Queue should not exceed max size
        queue_size = connector.get_queue_size()
        assert queue_size <= 5

        await connector.stop()
        start_task.cancel()


class TestDatAiConnector:
    """Test DatAI property price connector"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test connector initializes"""
        connector = DatAiConnector()
        assert connector.running is False
        assert connector.get_cache_size() == 0
        assert len(connector.get_tracked_locations()) == 0

    @pytest.mark.asyncio
    async def test_property_collection(self):
        """Test property listing collection"""
        connector = DatAiConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(3)

        assert connector.get_cache_size() > 0

        for prop_id, prop in connector.properties_cache.items():
            assert isinstance(prop, PropertyPrice)
            assert prop.property_id == prop_id
            assert prop.price_per_sqm > 0
            assert prop.total_price > 0
            assert prop.sqm > 0
            assert 0 <= prop.market_heat <= 1.0

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_location_trends(self):
        """Test location-level trend collection"""
        connector = DatAiConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(3)

        locations = connector.get_tracked_locations()
        assert len(locations) > 0

        for location in locations:
            trend = await connector.get_location_trend(location)
            assert trend is not None
            assert trend.location == location
            assert isinstance(trend.avg_price_per_sqm, float)
            assert -1.0 <= trend.market_momentum <= 1.0

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_get_properties_by_location(self):
        """Test filtering properties by location"""
        connector = DatAiConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(2)

        # Get properties for specific location
        properties = await connector.get_properties(location='Dong Nai')

        for prop in properties:
            assert prop.location == 'Dong Nai'

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_get_properties_by_type(self):
        """Test filtering properties by type"""
        connector = DatAiConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(2)

        # Get apartment listings
        apartments = await connector.get_properties(property_type='Apartment')

        for prop in apartments:
            assert prop.property_type == 'Apartment'

        await connector.stop()
        start_task.cancel()


class TestMarketConnector:
    """Test multi-market (US + VN) connector"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test connector initializes"""
        connector = MarketConnector()
        assert connector.running is False
        assert connector.get_us_cache_size() == 0
        assert connector.get_vn_cache_size() == 0

    @pytest.mark.asyncio
    async def test_us_market_collection(self):
        """Test US stock data collection"""
        connector = MarketConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(3)

        us_quotes = await connector.get_quotes(market='US')
        assert len(us_quotes) > 0

        for symbol, quote in us_quotes.items():
            assert isinstance(quote, StockQuote)
            assert quote.market == 'US'
            assert quote.symbol == symbol
            assert quote.price > 0
            assert quote.volume > 0

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_vn_market_collection(self):
        """Test VN stock data collection"""
        connector = MarketConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(3)

        vn_quotes = await connector.get_quotes(market='VN')
        assert len(vn_quotes) > 0

        for symbol, quote in vn_quotes.items():
            assert isinstance(quote, StockQuote)
            assert quote.market == 'VN'
            assert quote.symbol in [
                'VCB', 'BID', 'CTG', 'TCB',
                'VHM', 'BCG', 'DXG',
                'FPT', 'MWG', 'VNP',
                'PVD', 'PVS', 'GAS'
            ]

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_market_snapshots(self):
        """Test market snapshot creation"""
        connector = MarketConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(4)  # Let snapshots update

        us_snapshot = await connector.get_snapshot(market='US')
        if us_snapshot:
            assert us_snapshot.market == 'US'
            assert us_snapshot.index_symbol == 'SPY'
            assert isinstance(us_snapshot.change_pct, float)
            assert 0 <= us_snapshot.trend_strength <= 1.0

        vn_snapshot = await connector.get_snapshot(market='VN')
        if vn_snapshot:
            assert vn_snapshot.market == 'VN'
            assert vn_snapshot.index_symbol == 'VN-Index'
            assert isinstance(vn_snapshot.change_pct, float)

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_get_single_quote(self):
        """Test getting a single stock quote"""
        connector = MarketConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(2)

        # Get AAPL quote
        quote = await connector.get_quote('AAPL')
        if quote:
            assert quote.symbol == 'AAPL'
            assert quote.market == 'US'

        await connector.stop()
        start_task.cancel()


class TestConnectorIntegration:
    """Integration tests for all connectors"""

    @pytest.mark.asyncio
    async def test_multiple_connectors_concurrent(self):
        """Test running all connectors concurrently"""
        sentinel = SentinelConnector()
        datai = DatAiConnector()
        market = MarketConnector()

        # Start all concurrently
        tasks = [
            asyncio.create_task(sentinel.start()),
            asyncio.create_task(datai.start()),
            asyncio.create_task(market.start()),
        ]

        await asyncio.sleep(3)

        # Verify all are collecting
        assert sentinel.get_cache_size() > 0
        assert datai.get_cache_size() > 0
        assert market.get_us_cache_size() > 0

        # Stop all
        await asyncio.gather(
            sentinel.stop(),
            datai.stop(),
            market.stop()
        )

        for task in tasks:
            task.cancel()

    @pytest.mark.asyncio
    async def test_queue_non_blocking_reads(self):
        """Test non-blocking queue reads across connectors"""
        sentinel = SentinelConnector()
        start_task = asyncio.create_task(sentinel.start())

        await asyncio.sleep(2)

        # Rapid non-blocking reads
        for _ in range(5):
            data = await sentinel.get_data(timeout=0.1)
            # Should return quickly (data or None)

        await sentinel.stop()
        start_task.cancel()


# Fixtures for common setup
@pytest.fixture
async def sentinel_connector():
    """Provide a Sentinel connector"""
    connector = SentinelConnector()
    yield connector
    await connector.stop()


@pytest.fixture
async def datai_connector():
    """Provide a DatAI connector"""
    connector = DatAiConnector()
    yield connector
    await connector.stop()


@pytest.fixture
async def market_connector():
    """Provide a Market connector"""
    connector = MarketConnector()
    yield connector
    await connector.stop()
