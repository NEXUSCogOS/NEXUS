"""Integration tests for TRACK 4: Real-time Data Integration"""
import asyncio
import pytest
from systems.engineering_studio.studio_v3.execution import (
    AutonomousProjectExecutor,
    SentinelConnector,
    DatAiConnector,
    MarketConnector
)
from systems.engineering_studio.studio_v3.platforms import (
    ContentGenerator,
    VideoUploader,
    DataFeedConnector
)


class TestTrack4Integration:
    """Full integration tests for TRACK 4"""

    @pytest.mark.asyncio
    async def test_executor_with_data_connectors(self):
        """Test AutonomousProjectExecutor with data connectors"""
        executor = AutonomousProjectExecutor()

        # Start connectors
        await executor.start_data_connectors()
        assert executor.data_connectors_running is True

        # Let them collect data
        await asyncio.sleep(2)

        # Verify all connectors are active
        sentinel_data = executor.get_sentinel_trends()
        assert sentinel_data['cache_size'] >= 0

        datai_data = executor.get_datai_trends()
        assert datai_data['cache_size'] >= 0

        market_data = executor.get_market_data()
        assert market_data['us_cache_size'] >= 0
        assert market_data['vn_cache_size'] >= 0

        # Get live sentiment
        sentiment = await executor.get_live_sentiment()
        assert isinstance(sentiment, dict)

        # Stop connectors
        await executor.stop_data_connectors()
        assert executor.data_connectors_running is False

    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(self):
        """Test complete pipeline: data → content → upload"""
        # Initialize components
        executor = AutonomousProjectExecutor()
        content_gen = ContentGenerator()
        uploader = VideoUploader()
        data_connector = DataFeedConnector(content_gen)

        # Start data collection
        await executor.start_data_connectors()
        await data_connector.start()

        await asyncio.sleep(1)

        # Simulate getting trends from market connector
        market_data = executor.market_connector
        if market_data.us_quotes:
            trends = [
                {
                    'symbol': symbol,
                    'change_pct': quote.change_pct
                }
                for symbol, quote in list(market_data.us_quotes.items())[:3]
            ]

            # Process through content generator
            await data_connector.process_sentinel_trends(trends)

            # Get generated content
            contents = await data_connector.get_queued_content()

            if contents:
                # Upload videos
                results = await uploader.batch_upload(
                    contents,
                    auto_publish=True,
                    interval_minutes=0  # No delay for testing
                )

                assert len(results) > 0
                for result in results:
                    assert result.status in ['published', 'pending']

        await executor.stop_data_connectors()
        await data_connector.stop()

    @pytest.mark.asyncio
    async def test_concurrent_data_sources(self):
        """Test handling multiple data sources concurrently"""
        executor = AutonomousProjectExecutor()
        content_gen = ContentGenerator()
        data_connector = DataFeedConnector(content_gen)

        await executor.start_data_connectors()
        await data_connector.start()

        await asyncio.sleep(1)

        # Create test trends from different sources
        stock_trends = [
            {'symbol': 'AAPL', 'change_pct': 2.5},
            {'symbol': 'MSFT', 'change_pct': 1.8},
        ]

        realestate_trends = [
            {'location': 'Dong Nai', 'change_pct': 3.2},
            {'location': 'Ho Chi Minh', 'change_pct': -1.5},
        ]

        # Process concurrently
        await asyncio.gather(
            data_connector.process_sentinel_trends(stock_trends),
            data_connector.process_datai_trends(realestate_trends),
            return_exceptions=True
        )

        # Verify content was generated
        contents = await data_connector.get_queued_content()
        assert len(contents) > 0

        await executor.stop_data_connectors()
        await data_connector.stop()

    @pytest.mark.asyncio
    async def test_queue_overflow_handling(self):
        """Test system handles queue overflow gracefully"""
        sentinel = SentinelConnector(queue_size=5)
        start_task = asyncio.create_task(sentinel.start())

        await asyncio.sleep(2)

        # Queue should not exceed max size
        max_queue_size = sentinel.get_queue_size()
        assert max_queue_size <= 5

        await sentinel.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_non_blocking_data_retrieval(self):
        """Test non-blocking data retrieval doesn't block executor"""
        executor = AutonomousProjectExecutor()

        await executor.start_data_connectors()
        await asyncio.sleep(1)

        # Non-blocking calls should return quickly
        import time
        start = time.time()

        # Make multiple rapid non-blocking calls
        for _ in range(10):
            sentinel_data = executor.get_sentinel_trends()
            datai_data = executor.get_datai_trends()
            market_data = executor.get_market_data()
            sentiment = await executor.get_live_sentiment()

        elapsed = time.time() - start

        # All should complete in < 1 second
        assert elapsed < 1.0

        await executor.stop_data_connectors()

    @pytest.mark.asyncio
    async def test_sentiment_calculation(self):
        """Test live sentiment calculation from data streams"""
        executor = AutonomousProjectExecutor()

        await executor.start_data_connectors()
        await asyncio.sleep(2)

        sentiment = await executor.get_live_sentiment()

        # Sentiment should have reasonable values
        for key, value in sentiment.items():
            assert isinstance(value, float)
            assert -1.0 <= value <= 1.0

        await executor.stop_data_connectors()

    @pytest.mark.asyncio
    async def test_youtube_automation_full_flow(self):
        """Test complete YouTube automation flow"""
        content_gen = ContentGenerator()
        uploader = VideoUploader()
        data_connector = DataFeedConnector(content_gen)

        await data_connector.start()

        # Create daily digest from multiple trends
        all_trends = [
            {'symbol': 'AAPL', 'change_pct': 2.5},
            {'symbol': 'MSFT', 'change_pct': 1.8},
            {'symbol': 'GOOGL', 'change_pct': -1.2},
            {'symbol': 'TSLA', 'change_pct': 3.1},
            {'symbol': 'VCB', 'change_pct': 2.3},
        ]

        # Generate daily digest
        await data_connector.process_daily_digest(all_trends)

        # Get content
        contents = await data_connector.get_queued_content()
        assert len(contents) > 0

        # Upload all
        results = await uploader.batch_upload(
            contents,
            auto_publish=True,
            interval_minutes=0
        )

        assert len(results) == len(contents)

        # Verify uploads
        published = uploader.get_published_count()
        assert published > 0

        await data_connector.stop()

    @pytest.mark.asyncio
    async def test_scale_multiple_projects(self):
        """Test system can handle multiple projects with data connectors"""
        executor = AutonomousProjectExecutor()

        projects = [
            {
                'name': f'Project-{i}',
                'description': f'Test project {i}',
                'requirements': f'Project {i} requirements',
                'domain': 'optimization'
            }
            for i in range(3)
        ]

        # Start connectors
        await executor.start_data_connectors()

        # Execute projects
        results = []
        for project in projects:
            result = executor.execute_project(project)
            results.append(result)

        # Verify all projects completed
        assert len(results) == 3
        for result in results:
            assert result.success is True

        # Connectors should still be running
        assert executor.data_connectors_running is True

        await executor.stop_data_connectors()


# Performance benchmarks
class TestTrack4Performance:
    """Performance tests for TRACK 4"""

    @pytest.mark.asyncio
    async def test_data_ingestion_latency(self):
        """Test data ingestion latency is acceptable"""
        import time

        connector = SentinelConnector()
        start_task = asyncio.create_task(connector.start())

        await asyncio.sleep(1)

        # Measure retrieval latency
        start = time.time()
        data = await connector.get_data(timeout=1.0)
        latency = (time.time() - start) * 1000  # Convert to ms

        # Should be sub-100ms for non-blocking read
        assert latency < 100

        await connector.stop()
        start_task.cancel()

    @pytest.mark.asyncio
    async def test_concurrent_connector_throughput(self):
        """Test throughput with all connectors running"""
        import time

        sentinel = SentinelConnector()
        datai = DatAiConnector()
        market = MarketConnector()

        tasks = [
            asyncio.create_task(sentinel.start()),
            asyncio.create_task(datai.start()),
            asyncio.create_task(market.start()),
        ]

        start = time.time()
        await asyncio.sleep(2)
        elapsed = time.time() - start

        # All connectors should be collecting in parallel
        total_items = (
            sentinel.get_cache_size() +
            datai.get_cache_size() +
            market.get_us_cache_size() +
            market.get_vn_cache_size()
        )

        # Should have collected reasonable amount of data
        assert total_items > 0

        throughput = total_items / elapsed
        assert throughput > 1  # At least 1 item per second

        await asyncio.gather(sentinel.stop(), datai.stop(), market.stop())
        for task in tasks:
            task.cancel()

    @pytest.mark.asyncio
    async def test_content_generation_speed(self):
        """Test content generation performance"""
        import time

        gen = ContentGenerator()

        start = time.time()

        # Generate 10 videos
        for i in range(10):
            trend = {
                'type': 'stock',
                'symbol': f'TEST{i}',
                'change_pct': float(i - 5)
            }
            concept = await gen.generate_from_trend(trend)

        elapsed = time.time() - start

        # Should generate ~10 videos per second
        per_video = (elapsed / 10) * 1000  # ms per video
        assert per_video < 100  # Less than 100ms per video
