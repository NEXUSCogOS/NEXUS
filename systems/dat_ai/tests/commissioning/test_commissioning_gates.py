"""Commissioning tests: real network, real credentials, real bytes.

Marked ``external`` (network only) or ``commissioning`` (network + credentials
+ byte transfer). Both skip cleanly when their prerequisites are absent — they
never pass by pretending.

Run with::

    pytest tests/commissioning -m external      # Gate A, no credentials
    pytest tests/commissioning                  # all gates, needs credentials
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

# Phase C scope note (2026-08-27, DAT.AI Phase C canonical recovery): every
# test in this file exercises app.satellite.pipeline / app.satellite.aoi /
# tests/fixtures/stac_response.json -- all part of the satellite ACQUISITION
# pipeline, which is explicitly out of Phase C's recovery scope (it needs
# CDSE/Planet credentials confirmed NOT_FOUND anywhere in this estate during
# Phase A+B verification; see DATAI_COMPONENT_RECOVERY_MATRIX.md, MODERNIZE
# classification). This file is recovered as donor reference / forward-
# compatible test scaffolding for when Phase D recovers that pipeline, but it
# cannot be exercised until then. Skipping the whole module here reports that
# honestly (a clear SKIP with a stated reason) instead of showing
# ModuleNotFoundError as a scary, unexplained test ERROR.
pytest.importorskip(
    "app.satellite.pipeline",
    reason=(
        "app.satellite.pipeline is Phase D scope (satellite acquisition "
        "pipeline), not yet recovered into canonical NEXUS in Phase C"
    ),
)

from tests.conftest import (
    requires_cdse_credentials,
    requires_database,
    requires_network,
)

COMMISSIONING_PRODUCT = (
    "S2C_MSIL2A_20260720T030521_N0512_R075_T48PYS_20260720T082013"
)


# =====================================================================
# Gate A — catalogue discovery (network only, no credentials)
# =====================================================================


@pytest.mark.external
@requires_network
class TestGateADiscovery:
    @pytest.fixture(scope="class")
    def products(self, dong_nai_aoi):
        from app.config import settings
        from app.satellite.discovery import discover_sentinel_products

        end = datetime.utcnow().date()
        return discover_sentinel_products(
            aoi=dong_nai_aoi,
            start_time=end - timedelta(days=60),
            end_time=end,
            max_cloud_cover=30.0,
            config=settings,
        )

    def test_catalogue_returns_real_products(self, products):
        assert products, "CDSE STAC returned no products over the Dong Nai AOI"

    def test_products_are_sentinel_2_l2a(self, products):
        for product in products:
            assert product.collection == "sentinel-2-l2a"
            # CDSE reports processing:level as "L2" (not "L2A"); the L2A
            # distinction is carried by product:type / the product identifier.
            assert product.processing_level in ("L2", "L2A", None)
            assert "MSIL2A" in product.stac_id

    def test_discovered_tiles_are_the_real_ones_not_the_hardcoded_list(
        self, products
    ):
        """The old code hard-coded 48PVR/48PVS/48PWR/48PWS for Dong Nai."""
        tiles = {p.mgrs_tile for p in products if p.mgrs_tile}
        stale = {"48PVR", "48PVS", "48PWR", "48PWS"}
        assert tiles, "no MGRS tiles resolved"
        assert not (tiles & stale), (
            f"Catalogue returned a tile from the stale hard-coded list: "
            f"{tiles & stale}"
        )

    def test_cloud_filter_is_respected(self, products):
        for product in products:
            if product.cloud_cover is not None:
                assert product.cloud_cover <= 30.0

    def test_at_least_one_product_has_all_required_bands(self, products):
        complete = [p for p in products if not p.missing_required_assets()]
        assert complete, "No product exposes B02/B03/B04/B08 at 10 m"

    def test_assets_are_s3_uris_with_https_alternates(self, products):
        product = next(p for p in products if not p.missing_required_assets())
        asset = product.assets["B04_10m"]
        assert asset.s3_uri.startswith("s3://eodata/")
        assert asset.https_uri and asset.https_uri.startswith("https://")

    def test_discovery_downloads_nothing(self, products, tmp_path):
        """Discovery must remain metadata-only."""
        assert not list(tmp_path.iterdir())


# =====================================================================
# Gates B-D — real acquisition (needs credentials)
# =====================================================================


@pytest.mark.commissioning
@requires_network
@requires_cdse_credentials
class TestGatesBCDAcquisition:
    @pytest.fixture(scope="class")
    def product(self, dong_nai_aoi):
        from app.config import settings
        from app.satellite.discovery import discover_sentinel_products

        end = datetime.utcnow().date()
        candidates = [
            p
            for p in discover_sentinel_products(
                aoi=dong_nai_aoi,
                start_time=end - timedelta(days=90),
                end_time=end,
                max_cloud_cover=40.0,
                config=settings,
            )
            if not p.missing_required_assets()
        ]
        if not candidates:
            pytest.skip("no suitable product in the catalogue window")
        return min(candidates, key=lambda p: p.cloud_cover or 100)

    @pytest.fixture(scope="class")
    def acquirer(self):
        from app.config import settings
        from app.satellite.acquisition import AssetAcquirer

        return AssetAcquirer(settings)

    def test_gate_b_head_object_confirms_existence(self, acquirer, product):
        head = acquirer.head_asset(product.assets["B04_10m"])
        assert head.exists is True
        assert head.size_bytes and head.size_bytes > 1_000_000

    def test_gate_c_single_band_downloads_real_bytes(
        self, acquirer, product, tmp_path
    ):
        result = acquirer.acquire(product, ("B04_10m",), cache_dir=tmp_path)
        record = result.assets["B04_10m"]
        path = tmp_path / product.stac_id / record.filename
        assert path.exists()
        assert path.stat().st_size == record.size_bytes > 1_000_000
        assert len(record.sha256) == 64

    def test_gate_c_checksum_matches_disk(self, acquirer, product, tmp_path):
        from app.satellite.cache import sha256_of

        result = acquirer.acquire(product, ("B04_10m",), cache_dir=tmp_path)
        record = result.assets["B04_10m"]
        path = tmp_path / product.stac_id / record.filename
        assert sha256_of(path) == record.sha256

    def test_cache_reuse_avoids_a_second_download(
        self, acquirer, product, tmp_path
    ):
        first = acquirer.acquire(product, ("B04_10m",), cache_dir=tmp_path)
        second = acquirer.acquire(product, ("B04_10m",), cache_dir=tmp_path)
        assert first.bytes_downloaded > 0
        assert second.bytes_downloaded == 0
        assert second.bytes_from_cache == first.bytes_downloaded

    def test_gate_d_all_required_bands(self, acquirer, product, tmp_path):
        from app.satellite.discovery import MASK_ASSETS, REQUIRED_BAND_ASSETS

        keys = REQUIRED_BAND_ASSETS + MASK_ASSETS
        result = acquirer.acquire(product, keys, cache_dir=tmp_path)
        assert set(result.assets) == set(keys)
        for record in result.assets.values():
            assert record.size_bytes > 0


# =====================================================================
# Gates E-H — decode, preprocess, infer, vectorise (needs credentials)
# =====================================================================


@pytest.mark.commissioning
@requires_network
@requires_cdse_credentials
class TestGatesEFGH:
    @pytest.fixture(scope="class")
    def acquired(self, dong_nai_aoi, tmp_path_factory):
        from app.config import settings
        from app.satellite.acquisition import AssetAcquirer
        from app.satellite.discovery import (
            MASK_ASSETS,
            REQUIRED_BAND_ASSETS,
            discover_sentinel_products,
        )

        cache = tmp_path_factory.mktemp("commissioning_cache")
        end = datetime.utcnow().date()
        candidates = [
            p
            for p in discover_sentinel_products(
                aoi=dong_nai_aoi,
                start_time=end - timedelta(days=90),
                end_time=end,
                max_cloud_cover=40.0,
                config=settings,
            )
            if not p.missing_required_assets()
        ]
        if not candidates:
            pytest.skip("no suitable product")
        product = min(candidates, key=lambda p: p.cloud_cover or 100)
        AssetAcquirer(settings).acquire(
            product, REQUIRED_BAND_ASSETS + MASK_ASSETS, cache_dir=cache
        )
        return product, cache

    def test_gate_e_raster_metadata_is_valid(self, acquired):
        from app.satellite.cache import ProductCache
        from app.satellite.raster import read_metadata

        product, cache_dir = acquired
        cache = ProductCache(cache_dir, product)
        meta = read_metadata(cache.path_for("B04_10m"))

        assert meta.width == meta.height == 10980  # Sentinel-2 10 m tile
        assert meta.dtype == "uint16"
        assert meta.crs.startswith("EPSG:326")  # UTM north
        assert meta.resolution == pytest.approx((10.0, 10.0))
        assert meta.transform[0] == 10.0
        assert meta.count == 1

    def test_gate_e_bands_share_a_grid(self, acquired):
        from app.satellite.cache import ProductCache
        from app.satellite.discovery import REQUIRED_BAND_ASSETS
        from app.satellite.raster import read_metadata

        product, cache_dir = acquired
        cache = ProductCache(cache_dir, product)
        grids = {
            read_metadata(cache.path_for(key)).transform
            for key in REQUIRED_BAND_ASSETS
        }
        assert len(grids) == 1, "10 m bands must share one affine transform"

    def test_gate_f_preprocessing_produces_real_reflectance(self, acquired):
        from app.satellite.preprocess import preprocess_product

        product, cache_dir = acquired
        model_input = preprocess_product(
            product, cache_dir=cache_dir, window_size=512, window_offset=(5000, 5000)
        )
        assert model_input.data.shape == (4, 512, 512)
        assert model_input.data.dtype.name == "float32"
        assert 0.0 <= model_input.data.min() <= model_input.data.max() <= 1.0
        # Real imagery is not constant.
        assert model_input.data.std() > 0.001
        assert model_input.crs.startswith("EPSG:326")

    def test_gate_f_is_deterministic(self, acquired):
        import numpy as np

        from app.satellite.preprocess import preprocess_product

        product, cache_dir = acquired
        kwargs = dict(cache_dir=cache_dir, window_size=256, window_offset=(5000, 5000))
        first = preprocess_product(product, **kwargs)
        second = preprocess_product(product, **kwargs)
        assert np.array_equal(first.data, second.data)
        assert np.array_equal(first.valid_mask, second.valid_mask)

    def test_gate_f_records_every_transformation(self, acquired):
        from app.satellite.preprocess import preprocess_product

        product, cache_dir = acquired
        model_input = preprocess_product(
            product, cache_dir=cache_dir, window_size=256, window_offset=(5000, 5000)
        )
        joined = " ".join(model_input.transformations)
        assert "reflectance" in joined
        assert "SCL" in joined
        assert model_input.preprocessing_version

    def test_gate_g_inference_on_real_bands(self, acquired):
        from app.ml.satellite_classifier import load_classifier
        from app.satellite.preprocess import preprocess_product

        product, cache_dir = acquired
        model_input = preprocess_product(
            product, cache_dir=cache_dir, window_size=512, window_offset=(5000, 5000)
        )
        result = load_classifier().classify(
            model_input.data, valid_mask=model_input.valid_mask
        )
        assert result.class_map.shape == (512, 512)
        assert result.promotion_status.may_persist_observations is False

    def test_gate_h_geometry_lands_inside_the_product_footprint(self, acquired):
        from shapely.geometry import shape

        from app.ml.satellite_classifier import load_classifier
        from app.satellite.preprocess import preprocess_product
        from app.satellite.vectorise import (
            assert_plausible_location,
            vectorise_classification,
        )

        product, cache_dir = acquired
        model_input = preprocess_product(
            product, cache_dir=cache_dir, window_size=512, window_offset=(5000, 5000)
        )
        inference = load_classifier().classify(
            model_input.data, valid_mask=model_input.valid_mask
        )
        regions = vectorise_classification(
            class_map=inference.class_map,
            confidence_map=inference.confidence_map,
            valid_mask=model_input.valid_mask,
            transform=model_input.transform,
            crs=model_input.crs,
            class_names=inference.classes,
        )
        assert regions, "vectorisation produced no regions from real imagery"
        assert_plausible_location(regions, product.bbox)

        for region in regions:
            centroid = shape(region.geometry_4326).centroid
            assert 105 < centroid.x < 110
            assert 8 < centroid.y < 14
            assert region.area_sqm > 0


# =====================================================================
# Gate L — commit is refused while the model is unpromoted
# =====================================================================


@pytest.mark.integration
@requires_database
class TestGateLRefusesUnpromotedModel:
    @pytest.fixture
    def fixtures(self, stac_fixture, tmp_path):
        """A real parsed product plus a plausible region, no imagery needed."""
        from app.satellite.discovery import parse_stac_item
        from app.satellite.vectorise import ClassRegion

        product = parse_stac_item(
            stac_fixture["features"][0],
            "https://stac.dataspace.copernicus.eu/v1/search",
        )
        min_x, min_y, _, _ = product.bbox
        region = ClassRegion(
            land_use_class="urban",
            confidence=0.91,
            area_sqm=45_000.0,
            geometry_4326={
                "type": "Polygon",
                "coordinates": [
                    [
                        [min_x + 0.01, min_y + 0.01],
                        [min_x + 0.02, min_y + 0.01],
                        [min_x + 0.02, min_y + 0.02],
                        [min_x + 0.01, min_y + 0.02],
                        [min_x + 0.01, min_y + 0.01],
                    ]
                ],
            },
            source_crs="EPSG:32648",
            pixel_count=450,
        )
        return product, region, tmp_path

    def test_gate_l_commit_raises_model_not_promoted(self, db_session, fixtures):
        """The central safety property: no fabricated intelligence.

        Exercises the real ``gate_l_commit`` path. The refusal is decided by
        the model audit, so it needs neither credentials nor network.
        """
        from app.config import settings
        from app.ml.satellite_classifier import audit_only
        from app.satellite.pipeline import Gate, SatellitePipeline

        audit = audit_only(settings)
        assert audit.promotion_status.may_persist_observations is False

        product, region, cache_dir = fixtures
        pipeline = SatellitePipeline(db_session, settings)

        class _Inference:
            model_version = audit.model_version
            model_sha256 = audit.sha256
            promotion_status = audit.promotion_status
            classes = ("urban", "agricultural", "water", "forest", "vacant")

        outcome = pipeline.gate_l_commit(
            product, [region], _Inference(), "dong_nai", cache_dir
        )

        assert outcome.gate is Gate.L_COMMIT
        assert outcome.passed is False
        assert outcome.failure_class == "model_not_promoted"
        assert "UNTRAINED" in outcome.detail

    def test_no_layers_are_written_by_the_refused_commit(
        self, db_session, fixtures
    ):
        from sqlalchemy import text

        from app.config import settings
        from app.ml.satellite_classifier import audit_only
        from app.satellite.pipeline import SatellitePipeline

        audit = audit_only(settings)
        product, region, cache_dir = fixtures
        pipeline = SatellitePipeline(db_session, settings)

        class _Inference:
            model_version = audit.model_version
            model_sha256 = audit.sha256
            promotion_status = audit.promotion_status
            classes = ("urban",)

        pipeline.gate_l_commit(
            product, [region], _Inference(), "dong_nai", cache_dir
        )

        count = db_session.execute(
            text("SELECT COUNT(*) FROM satellite_layers WHERE run_id = :rid"),
            {"rid": str(pipeline.run_id)},
        ).scalar()
        assert count == 0

    def test_refusal_is_recorded_in_the_ingest_log(self, db_session, fixtures):
        from sqlalchemy import text

        from app.config import settings
        from app.ml.satellite_classifier import audit_only
        from app.satellite.pipeline import SatellitePipeline

        audit = audit_only(settings)
        product, region, cache_dir = fixtures
        pipeline = SatellitePipeline(db_session, settings)

        class _Inference:
            model_version = audit.model_version
            model_sha256 = audit.sha256
            promotion_status = audit.promotion_status
            classes = ("urban",)

        pipeline.gate_l_commit(
            product, [region], _Inference(), "dong_nai", cache_dir
        )

        row = db_session.execute(
            text(
                "SELECT ingestion_status, failure_class FROM satellite_ingest_log "
                "WHERE run_id = :rid ORDER BY id DESC LIMIT 1"
            ),
            {"rid": str(pipeline.run_id)},
        ).first()
        assert row is not None
        assert row[0] == "skipped_model_not_promoted"
        assert row[1] == "model_not_promoted"


# =====================================================================
# Full pipeline dry run
# =====================================================================


@pytest.mark.external
@pytest.mark.integration
@requires_network
@requires_database
class TestPipelineDryRun:
    def test_dry_run_reaches_gate_a_and_writes_no_layers(self, db_session):
        from app.config import settings
        from app.satellite.pipeline import Gate, SatellitePipeline

        pipeline = SatellitePipeline(db_session, settings)
        result = pipeline.run(dry_run=True, days_back=60)

        assert result.last_gate is Gate.A_DISCOVERY
        assert result.gates[0].passed is True
        assert result.products_discovered > 0
        assert result.layers_written == 0
        assert result.bytes_downloaded == 0
        assert result.committed is False

    def test_commission_one_fails_closed_without_credentials(self, db_session):
        from app.config import settings

        if settings.has_any_acquisition_credentials:
            pytest.skip("credentials present; this test covers their absence")

        from app.satellite.pipeline import Gate, SatellitePipeline

        result = SatellitePipeline(db_session, settings).run(
            dry_run=False, commit=False, days_back=60
        )

        assert result.passed is False
        failure = result.failure
        assert failure is not None
        assert failure.gate is Gate.B_ASSET_HEAD
        assert failure.failure_class == "credentials_missing"
        assert result.layers_written == 0
        assert result.committed is False
