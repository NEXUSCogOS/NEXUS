"""Compression pipeline for tiered storage.

Three real strategies, chosen by file type:
  - GZIP:      single JSON/text/log files -> ``<name>.gz``
  - ZIP:       mixed directories / bundles -> ``<name>.zip`` (supports
               just-in-time extraction of a single member without
               unpacking the whole archive)
  - SQLITE_GZ: SQLite database files -> ``<name>.sqlite3.gz`` (checkpoints
               WAL first so the gzip captures a consistent, single-file
               snapshot)

Every ``compress()`` call measures real before/after sizes via
``measure_storage_delta`` (actual ``os.stat`` calls, not estimates) so the
reported compression ratio is independently verifiable.
"""

from __future__ import annotations

import gzip
import shutil
import sqlite3
import zipfile
from enum import Enum
from pathlib import Path

from systems.engineering_studio.studio_v3.observatory import measure_storage_delta

_TEXT_SUFFIXES = {".json", ".txt", ".log", ".md", ".csv", ".jsonl", ".yaml", ".yml"}
_SQLITE_SUFFIXES = {".sqlite3", ".sqlite", ".db"}


class CompressionStrategy(str, Enum):
    GZIP = "gzip"
    ZIP = "zip"
    SQLITE3_GZ = "sqlite3_gz"


class CompressionPipeline:
    """Compresses files using a strategy appropriate to their type, and
    supports just-in-time decompression (extract-one-member, not the whole
    archive) so cold-tier reads don't require rehydrating everything.
    """

    @staticmethod
    def choose_strategy(path: str | Path, *, is_bundle: bool = False) -> CompressionStrategy:
        p = Path(path)
        if p.suffix.lower() in _SQLITE_SUFFIXES:
            return CompressionStrategy.SQLITE3_GZ
        if is_bundle or p.is_dir():
            return CompressionStrategy.ZIP
        if p.suffix.lower() in _TEXT_SUFFIXES:
            return CompressionStrategy.GZIP
        # Default: zip, since it's the only strategy that safely handles
        # arbitrary/unknown binary content as a single-member archive.
        return CompressionStrategy.ZIP

    def compress(
        self,
        path: str | Path,
        dest_dir: str | Path,
        *,
        strategy: CompressionStrategy | None = None,
    ) -> dict:
        """Compress `path` into `dest_dir`, returning a measurement dict:
        {strategy, source_path, compressed_path, size_before, size_after,
         ratio, saved_bytes}. All sizes come from real on-disk measurement.
        """
        src = Path(path)
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        chosen = strategy or self.choose_strategy(src, is_bundle=src.is_dir())
        before = measure_storage_delta(src)

        if chosen is CompressionStrategy.GZIP:
            compressed_path = dest_dir / (src.name + ".gz")
            with open(src, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        elif chosen is CompressionStrategy.SQLITE3_GZ:
            compressed_path = dest_dir / (src.name + ".gz")
            self._checkpoint_wal(src)
            with open(src, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        elif chosen is CompressionStrategy.ZIP:
            compressed_path = dest_dir / (src.name + ".zip")
            with zipfile.ZipFile(compressed_path, "w", zipfile.ZIP_DEFLATED) as zf:
                if src.is_dir():
                    for member in sorted(src.rglob("*")):
                        if member.is_file():
                            zf.write(member, arcname=str(member.relative_to(src.parent)))
                else:
                    zf.write(src, arcname=src.name)
        else:  # pragma: no cover - exhaustive enum
            raise ValueError(f"Unknown compression strategy: {chosen}")

        after = measure_storage_delta(compressed_path)
        size_before = before["size_bytes"]
        size_after = after["size_bytes"]
        saved_bytes = size_before - size_after
        ratio = (saved_bytes / size_before) if size_before else 0.0

        return {
            "strategy": chosen.value,
            "source_path": str(src),
            "compressed_path": str(compressed_path),
            "size_before": size_before,
            "size_after": size_after,
            "saved_bytes": saved_bytes,
            "ratio": ratio,
            "measured_at": after["measured_at"],
        }

    @staticmethod
    def _checkpoint_wal(sqlite_path: Path) -> None:
        """Run a WAL checkpoint so the on-disk file is a consistent snapshot
        before it gets gzipped (otherwise a concurrent writer's WAL file
        would be silently excluded from the archive).
        """
        try:
            conn = sqlite3.connect(str(sqlite_path))
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.commit()
            conn.close()
        except sqlite3.Error:
            # Not every *.db file is actually a SQLite database (e.g. a
            # LevelDB .db directory would never reach here since is_dir()
            # routes to ZIP) — best-effort only, compression still proceeds.
            pass

    def decompress_jit(
        self,
        archive_path: str | Path,
        *,
        member_name: str | None = None,
        strategy: CompressionStrategy | None = None,
    ) -> bytes:
        """Just-in-time decompression: return the bytes of a single file
        without rehydrating the whole archive to disk.

        For GZIP/SQLITE3_GZ archives (single-member by construction),
        `member_name` is ignored. For ZIP archives, `member_name` selects
        which entry to read out of the zip's central directory.
        """
        archive_path = Path(archive_path)
        chosen = strategy or self._infer_strategy_from_suffix(archive_path)

        if chosen in (CompressionStrategy.GZIP, CompressionStrategy.SQLITE3_GZ):
            with gzip.open(archive_path, "rb") as f:
                return f.read()

        if chosen is CompressionStrategy.ZIP:
            with zipfile.ZipFile(archive_path, "r") as zf:
                if member_name is None:
                    names = zf.namelist()
                    if len(names) != 1:
                        raise ValueError(
                            "member_name is required for a multi-member zip archive "
                            f"({archive_path}, {len(names)} members)"
                        )
                    member_name = names[0]
                return zf.read(member_name)

        raise ValueError(f"Unknown compression strategy: {chosen}")  # pragma: no cover

    def decompress_jit_to_file(
        self,
        archive_path: str | Path,
        target_dir: str | Path,
        *,
        member_name: str | None = None,
        strategy: CompressionStrategy | None = None,
    ) -> Path:
        """Like decompress_jit, but writes the recovered bytes to a real
        temp/target file and returns its path — useful when the caller
        needs a sqlite3.connect()-able path rather than raw bytes.
        """
        data = self.decompress_jit(archive_path, member_name=member_name, strategy=strategy)
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        name = member_name or Path(archive_path).stem
        out_path = target_dir / name
        out_path.write_bytes(data)
        return out_path

    @staticmethod
    def _infer_strategy_from_suffix(archive_path: Path) -> CompressionStrategy:
        suffixes = archive_path.suffixes
        if archive_path.suffix == ".zip":
            return CompressionStrategy.ZIP
        if len(suffixes) >= 2 and suffixes[-2] in _SQLITE_SUFFIXES and suffixes[-1] == ".gz":
            return CompressionStrategy.SQLITE3_GZ
        if archive_path.suffix == ".gz":
            return CompressionStrategy.GZIP
        raise ValueError(f"Cannot infer compression strategy from suffix: {archive_path}")
