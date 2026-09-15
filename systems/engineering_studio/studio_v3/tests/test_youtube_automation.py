"""Tests for YouTube automation pipeline (TRACK 4)"""
import asyncio
import pytest
from datetime import datetime
from systems.engineering_studio.studio_v3.platforms import (
    ContentGenerator,
    VideoUploader,
    DataFeedConnector,
    VideoConcept,
    VideoContent
)


class TestContentGenerator:
    """Test video concept generation"""

    def test_initialization(self):
        """Test generator initializes"""
        gen = ContentGenerator()
        assert len(gen.generation_history) == 0
        assert len(gen.concept_cache) == 0

    @pytest.mark.asyncio
    async def test_generate_from_project(self):
        """Test generating concepts from projects"""
        gen = ContentGenerator()

        project = {
            'name': 'NEXUS Optimization',
            'description': 'Complete NEXUS system optimization',
            'results': {
                'performance_improvement': 10,
                'code_reduction': 35,
                'tests_passing': True,
                'test_count': 77
            }
        }

        concept = await gen.generate_from_project(project)

        assert isinstance(concept, VideoConcept)
        assert 'NEXUS Optimization' in concept.title
        assert concept.duration_estimate == 600
        assert concept.category == 'Science & Technology'
        assert len(concept.key_points) >= 3
        assert concept.confidence_score > 0.8
        assert 'engineering' in concept.tags

    @pytest.mark.asyncio
    async def test_generate_from_stock_trend(self):
        """Test generating concepts from stock trends"""
        gen = ContentGenerator()

        trend = {
            'type': 'stock',
            'symbol': 'AAPL',
            'change_pct': 3.5
        }

        concept = await gen.generate_from_trend(trend)

        assert 'AAPL' in concept.title
        assert 'rallying' in concept.title.lower()
        assert concept.category == 'Finance'
        assert '3.5' in concept.title
        assert 'stock-market' in concept.tags
        assert len(concept.key_points) >= 3

    @pytest.mark.asyncio
    async def test_generate_from_declining_trend(self):
        """Test generating concepts from declining trends"""
        gen = ContentGenerator()

        trend = {
            'type': 'stock',
            'symbol': 'TSLA',
            'change_pct': -2.1
        }

        concept = await gen.generate_from_trend(trend)

        assert 'TSLA' in concept.title
        assert 'declining' in concept.title.lower()
        assert '-2.1' in concept.title or '2.1' in concept.title

    @pytest.mark.asyncio
    async def test_generate_from_real_estate_trend(self):
        """Test generating concepts from real estate trends"""
        gen = ContentGenerator()

        trend = {
            'type': 'real_estate',
            'location': 'Ho Chi Minh',
            'change_pct': 5.2
        }

        concept = await gen.generate_from_trend(trend)

        assert 'Ho Chi Minh' in concept.title
        assert 'Real Estate' in concept.title
        assert concept.category == 'Finance'
        assert 'real-estate' in concept.tags
        assert 'ho-chi-minh' in concept.tags

    @pytest.mark.asyncio
    async def test_generate_daily_digest(self):
        """Test generating daily digest videos"""
        gen = ContentGenerator()

        trends = [
            {'symbol': 'AAPL', 'change_pct': 2.5},
            {'symbol': 'MSFT', 'change_pct': 1.8},
            {'symbol': 'GOOGL', 'change_pct': -1.2},
            {'symbol': 'VCB', 'change_pct': 3.1},
            {'symbol': 'BCG', 'change_pct': -0.5},
        ]

        concepts = await gen.generate_daily_digest(trends)

        assert len(concepts) > 0
        assert concepts[0].title == "Market Digest: Top 3 Movers Today"
        assert concepts[0].duration_estimate == 180
        assert len(concepts[0].key_points) >= 3
        assert concepts[0].confidence_score > 0.8

    def test_generation_history(self):
        """Test tracking generation history"""
        gen = ContentGenerator()

        concept1 = VideoConcept(
            title='Test 1',
            description='',
            tags=[],
            category='',
            duration_estimate=0,
            hook_line='',
            key_points=[],
            call_to_action='',
            trend_source='test',
            confidence_score=0.5
        )
        gen.generation_history.append(concept1)

        history = gen.get_generation_history()
        assert len(history) == 1
        assert history[0].title == 'Test 1'

    def test_concept_caching(self):
        """Test concept caching"""
        gen = ContentGenerator()

        concept = VideoConcept(
            title='Test',
            description='',
            tags=[],
            category='',
            duration_estimate=0,
            hook_line='',
            key_points=[],
            call_to_action='',
            trend_source='test:key',
            confidence_score=0.5
        )

        gen.concept_cache['test:key'] = concept
        retrieved = gen.get_concept('test:key')

        assert retrieved is not None
        assert retrieved.title == 'Test'


class TestVideoUploader:
    """Test video upload functionality"""

    def test_initialization(self):
        """Test uploader initializes"""
        uploader = VideoUploader()
        assert len(uploader.uploaded_videos) == 0
        assert uploader.api_key is None

    @pytest.mark.asyncio
    async def test_upload_video(self):
        """Test uploading a video"""
        uploader = VideoUploader()

        concept = VideoConcept(
            title='Test Video',
            description='Test description',
            tags=['test'],
            category='Science & Technology',
            duration_estimate=300,
            hook_line='Hook',
            key_points=['Point 1'],
            call_to_action='Subscribe',
            trend_source='test',
            confidence_score=0.8
        )

        content = VideoContent(
            concept=concept,
            script='Test script',
            thumbnail_prompt='Test thumbnail'
        )

        result = await uploader.upload_video(content, auto_publish=True)

        assert result.status == 'published'
        assert result.title == 'Test Video'
        assert 'youtube' in result.url.lower()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_upload_with_pending_status(self):
        """Test uploading with pending status"""
        uploader = VideoUploader()

        concept = VideoConcept(
            title='Pending Video',
            description='',
            tags=[],
            category='',
            duration_estimate=0,
            hook_line='',
            key_points=[],
            call_to_action='',
            trend_source='test',
            confidence_score=0.8
        )

        content = VideoContent(
            concept=concept,
            script='',
            thumbnail_prompt=''
        )

        result = await uploader.upload_video(content, auto_publish=False)

        assert result.status == 'pending'

    @pytest.mark.asyncio
    async def test_batch_upload(self):
        """Test batch uploading videos"""
        uploader = VideoUploader()

        contents = []
        for i in range(3):
            concept = VideoConcept(
                title=f'Video {i}',
                description='',
                tags=[],
                category='',
                duration_estimate=0,
                hook_line='',
                key_points=[],
                call_to_action='',
                trend_source='test',
                confidence_score=0.8
            )
            contents.append(VideoContent(
                concept=concept,
                script='',
                thumbnail_prompt=''
            ))

        results = await uploader.batch_upload(contents, auto_publish=True, interval_minutes=1)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert f'Video {i}' in result.title
            assert result.status == 'published'

    def test_upload_history(self):
        """Test tracking upload history"""
        uploader = VideoUploader()

        # Manually add some results
        from systems.engineering_studio.studio_v3.platforms.youtube_automation import UploadResult
        result = UploadResult(
            video_id='test123',
            title='Test',
            url='https://youtube.com/watch?v=test123',
            status='published',
            uploaded_at=datetime.now()
        )
        uploader.uploaded_videos.append(result)

        history = uploader.get_upload_history()
        assert len(history) == 1
        assert history[0].video_id == 'test123'

    def test_published_count(self):
        """Test counting published videos"""
        uploader = VideoUploader()

        from systems.engineering_studio.studio_v3.platforms.youtube_automation import UploadResult
        for i in range(3):
            status = 'published' if i < 2 else 'pending'
            uploader.uploaded_videos.append(UploadResult(
                video_id=f'test{i}',
                title=f'Video {i}',
                url='',
                status=status,
                uploaded_at=datetime.now()
            ))

        assert uploader.get_published_count() == 2


class TestDataFeedConnector:
    """Test data feed to video generation connector"""

    def test_initialization(self):
        """Test connector initializes"""
        gen = ContentGenerator()
        connector = DataFeedConnector(gen)

        assert connector.running is False
        assert connector.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping"""
        gen = ContentGenerator()
        connector = DataFeedConnector(gen)

        await connector.start()
        assert connector.running is True

        await connector.stop()
        assert connector.running is False

    @pytest.mark.asyncio
    async def test_process_sentinel_trends(self):
        """Test processing Sentinel market trends"""
        gen = ContentGenerator()
        connector = DataFeedConnector(gen)

        await connector.start()

        trends = [
            {'symbol': 'AAPL', 'change_pct': 2.5},
            {'symbol': 'MSFT', 'change_pct': 1.8},
        ]

        await connector.process_sentinel_trends(trends)

        queued = await connector.get_queued_content()
        assert len(queued) == 2

        for content in queued:
            assert isinstance(content, VideoContent)
            assert content.concept.category == 'Finance'
            assert len(content.script) > 0

        await connector.stop()

    @pytest.mark.asyncio
    async def test_process_datai_trends(self):
        """Test processing real estate trends"""
        gen = ContentGenerator()
        connector = DataFeedConnector(gen)

        await connector.start()

        trends = [
            {'location': 'Dong Nai', 'change_pct': 3.2},
            {'location': 'Ho Chi Minh', 'change_pct': -1.5},
        ]

        await connector.process_datai_trends(trends)

        queued = await connector.get_queued_content()
        assert len(queued) == 2

        for content in queued:
            assert isinstance(content, VideoContent)
            assert 'Real Estate' in content.concept.title

        await connector.stop()

    @pytest.mark.asyncio
    async def test_process_daily_digest(self):
        """Test processing daily digest"""
        gen = ContentGenerator()
        connector = DataFeedConnector(gen)

        await connector.start()

        trends = [
            {'symbol': 'AAPL', 'change_pct': 2.5},
            {'symbol': 'MSFT', 'change_pct': 1.8},
            {'symbol': 'GOOGL', 'change_pct': -1.2},
        ]

        await connector.process_daily_digest(trends)

        queued = await connector.get_queued_content()
        assert len(queued) > 0
        assert 'Digest' in queued[0].concept.title or 'daily' in queued[0].concept.title.lower()

        await connector.stop()

    @pytest.mark.asyncio
    async def test_queue_management(self):
        """Test queue management"""
        gen = ContentGenerator()
        connector = DataFeedConnector(gen)

        await connector.start()

        # Add some content
        trends = [
            {'symbol': f'TEST{i}', 'change_pct': float(i)}
            for i in range(5)
        ]

        await connector.process_sentinel_trends(trends)

        # Queue should have items
        queue_size = connector.get_queue_size()
        assert queue_size > 0

        await connector.stop()


class TestYouTubeIntegration:
    """Integration tests for full YouTube pipeline"""

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """Test full pipeline: generate → queue → upload"""
        gen = ContentGenerator()
        uploader = VideoUploader()
        connector = DataFeedConnector(gen)

        await connector.start()

        # Generate from trends
        trends = [
            {'symbol': 'VCB', 'change_pct': 4.2},
            {'symbol': 'BCG', 'change_pct': -1.8},
        ]

        await connector.process_sentinel_trends(trends)

        # Get queued content
        contents = await connector.get_queued_content()
        assert len(contents) > 0

        # Upload videos
        results = await uploader.batch_upload(
            contents, auto_publish=True, interval_minutes=1
        )

        assert len(results) == len(contents)
        for result in results:
            assert result.status == 'published'

        await connector.stop()

    @pytest.mark.asyncio
    async def test_multi_source_pipeline(self):
        """Test pipeline with multiple data sources"""
        gen = ContentGenerator()
        connector = DataFeedConnector(gen)
        uploader = VideoUploader()

        await connector.start()

        # Process from multiple sources
        stock_trends = [
            {'symbol': 'AAPL', 'change_pct': 2.5},
        ]
        realestate_trends = [
            {'location': 'Hanoi', 'change_pct': 2.1},
        ]

        await connector.process_sentinel_trends(stock_trends)
        await connector.process_datai_trends(realestate_trends)

        contents = await connector.get_queued_content()
        assert len(contents) == 2

        # Verify content diversity
        categories = [c.concept.category for c in contents]
        assert 'Finance' in categories

        await connector.stop()
