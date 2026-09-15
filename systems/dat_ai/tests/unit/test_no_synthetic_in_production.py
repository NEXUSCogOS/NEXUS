"""Source-level guard against simulated data returning to production paths.

These tests scan the shipped source. They exist because the specific defects
they check for were all present and were all invisible to type checkers and to
any test that only exercised the happy path.

If a future change reintroduces one of these patterns, this test fails and
names the file and line.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

APP_DIR = Path(__file__).resolve().parents[2] / "backend" / "app"

# Modules that may legitimately mention these patterns in prose (docstrings and
# comments explaining what was removed). Code is still checked; text is not.
PRODUCTION_MODULES = sorted(APP_DIR.rglob("*.py"))


def _source_files() -> list[Path]:
    return [p for p in PRODUCTION_MODULES if "__pycache__" not in p.parts]


def _code_only(path: Path) -> str:
    """Return the module's source with docstrings and comments removed."""
    text = path.read_text()
    tree = ast.parse(text)

    docstring_spans: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and first.end_lineno:
                    docstring_spans.update(
                        range(first.lineno, first.end_lineno + 1)
                    )

    kept = []
    for number, line in enumerate(text.splitlines(), start=1):
        if number in docstring_spans:
            continue
        stripped = line.split("#", 1)[0]
        kept.append(stripped)
    return "\n".join(kept)


class TestNoRandomDataGeneration:
    """The old pipeline used np.random.randint to stand in for Sentinel-2."""

    FORBIDDEN = (
        re.compile(r"\bnp\.random\.(randint|uniform|rand|normal|choice)\b"),
        re.compile(r"\bnumpy\.random\."),
        re.compile(r"\brandom\.(uniform|randint|choice|random)\b"),
    )

    def test_no_random_generation_in_app_code(self):
        offences: list[str] = []
        for path in _source_files():
            code = _code_only(path)
            for number, line in enumerate(code.splitlines(), start=1):
                for pattern in self.FORBIDDEN:
                    if pattern.search(line):
                        offences.append(f"{path.relative_to(APP_DIR)}:{number}: {line.strip()}")
        # random.uniform is permitted ONLY for retry jitter, which never
        # produces data. Allow it explicitly where it is provably jitter.
        offences = [o for o in offences if "backoff" not in o and "jitter" not in o]
        assert not offences, (
            "Random data generation found in application code:\n"
            + "\n".join(offences)
        )


class TestNoPlaceholderGeometry:
    """The old pipeline wrote POLYGON((0 0, w 0, w h, 0 h, 0 0))."""

    def test_no_hardcoded_wkt_polygon_literals(self):
        pattern = re.compile(r"POLYGON\s*\(\(", re.IGNORECASE)
        offences = [
            f"{path.relative_to(APP_DIR)}"
            for path in _source_files()
            if pattern.search(_code_only(path))
        ]
        assert not offences, f"Hard-coded WKT polygon literal in: {offences}"

    def test_no_origin_coordinates(self):
        """A polygon anchored at (0 0) is the signature of the old placeholder."""
        pattern = re.compile(r"\(\(\s*0\s+0\s*,")
        offences = [
            f"{path.relative_to(APP_DIR)}"
            for path in _source_files()
            if pattern.search(_code_only(path))
        ]
        assert not offences, f"Placeholder origin geometry in: {offences}"


class TestNoFakeStorageSuccess:
    """The old pipeline logged 'Stored X to S3' with put_object commented out."""

    def test_no_commented_out_upload_calls(self):
        pattern = re.compile(r"^\s*#\s*.*\b(put_object|upload_file|upload_fileobj)\b")
        offences = []
        for path in _source_files():
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if pattern.match(line):
                    offences.append(f"{path.relative_to(APP_DIR)}:{number}")
        assert not offences, (
            f"Commented-out upload next to live code in: {offences}. "
            "A disabled upload must not sit alongside a success log."
        )

    def test_no_simulate_or_for_now_markers_in_code(self):
        pattern = re.compile(
            r"\b(simulate storage|for now:?\s*simulate|fake success)\b",
            re.IGNORECASE,
        )
        offences = [
            f"{path.relative_to(APP_DIR)}"
            for path in _source_files()
            if pattern.search(_code_only(path))
        ]
        assert not offences, f"Simulation markers in: {offences}"


class TestNoFakePlanetFallback:
    """The old code fabricated planet_{lat}_{lng}_{date} scene identifiers."""

    def test_no_fabricated_planet_identifiers(self):
        pattern = re.compile(r"f?['\"]planet_\{")
        offences = [
            f"{path.relative_to(APP_DIR)}"
            for path in _source_files()
            if pattern.search(_code_only(path))
        ]
        assert not offences, f"Fabricated Planet identifier in: {offences}"

    @pytest.mark.skip(
        reason=(
            "app.satellite.planet is not part of DAT.AI Phase C's recovery "
            "scope -- it belongs to the satellite acquisition pipeline "
            "(MODERNIZE-classified), which requires Planet Labs credentials "
            "confirmed NOT_FOUND anywhere in this estate during Phase A+B. "
            "Re-enable when satellite/planet.py is recovered in a future "
            "phase. See DATAI_PHASE_D_ENTRY_CRITERIA.md."
        )
    )
    def test_planet_module_has_no_fallback_function(self):
        from app.satellite import planet

        assert not hasattr(planet, "_query_planet_imagery_fallback")
        assert not any(
            "fallback" in name.lower() for name in dir(planet)
        ), "Planet module must have no fallback path that invents scenes"

    @pytest.mark.skip(
        reason=(
            "app.satellite.planet is not part of DAT.AI Phase C's recovery "
            "scope -- see test_planet_module_has_no_fallback_function above "
            "for the full reason."
        )
    )
    def test_unconfigured_planet_reports_not_configured(self, test_settings):
        from dataclasses import replace

        from app.satellite.planet import PlanetAvailability, PlanetValidationSource

        source = PlanetValidationSource(replace(test_settings, planet_api_key=""))
        result = source.availability()
        assert result.availability is PlanetAvailability.NOT_CONFIGURED
        assert result.scenes == []
        assert "fabricat" in (result.reason or "").lower()


class TestNoHardcodedTileList:
    """The old pipeline hard-coded 48PVR/48PVS/48PWR/48PWS for Dong Nai.

    The catalogue returns 48PXS/48PXT/48PYS/48PYT for that AOI. None of the
    hard-coded tiles are correct.
    """

    STALE_TILES = ("48PVR", "48PVS", "48PWR", "48PWS", "48PUR", "48PUS")

    def test_no_stale_tile_identifiers_in_code(self):
        offences = []
        for path in _source_files():
            code = _code_only(path)
            for tile in self.STALE_TILES:
                if tile in code:
                    offences.append(f"{path.relative_to(APP_DIR)}: {tile}")
        assert not offences, (
            "Hard-coded MGRS tile identifiers found — tiles must be discovered "
            f"spatially from the AOI: {offences}"
        )


class TestNoBareExceptionSwallowing:
    """`except Exception: return <plausible value>` is how fake success hides."""

    def test_classifier_has_no_dummy_model_fallback(self):
        from app.ml import satellite_classifier

        assert not hasattr(satellite_classifier, "_create_dummy_model")
        source = _code_only(Path(satellite_classifier.__file__))
        assert "dummy" not in source.lower(), (
            "Classifier must raise when it cannot load, not invent a model"
        )

    def test_classify_does_not_return_zeros_on_error(self):
        from app.ml import satellite_classifier

        source = _code_only(Path(satellite_classifier.__file__))
        assert "np.zeros_like" not in source, (
            "Returning a zero class map on failure makes every pixel class 0"
        )
