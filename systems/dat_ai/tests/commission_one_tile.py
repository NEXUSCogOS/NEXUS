#!/usr/bin/env python3

from app.agents.satellite_agent import SatelliteIngestPipeline


def main():
    tile = "48PVR"

    p = SatelliteIngestPipeline()

    try:
        print("DAT.AI ONE-TILE COMMISSIONING")
        print("tile:", tile)

        result = p._fetch_copernicus_tile(tile)

        if not result:
            raise SystemExit("FAIL: real CDSE discovery returned no product")

        assert result.get("source") == "copernicus_cdse_stac"
        assert result.get("stac_id")
        assert result.get("metadata_only") is True
        assert result.get("assets")

        print("PASS: real catalogue discovery")
        print("stac_id:", result["stac_id"])
        print("cloud_cover:", result.get("cloud_cover"))
        print("assets:", len(result["assets"]))

        print()
        print("NO DATABASE WRITES PERFORMED")
        print("NO RANDOM CLASSIFICATION PERFORMED")
        print("NO SIMULATED S3 STORAGE PERFORMED")

    finally:
        p.session.close()


if __name__ == "__main__":
    main()
