#!/usr/bin/env python3
"""Process B (YouTube side): claim the mission, build the evidence pack
and claim ledger, generate and fact-check the script, produce real media
(voice, visual, render, thumbnail, metadata), run editorial QC, and
persist an InstitutionalReport into the SAME federation store DAT.AI/
Librarian/Sentinel/News already use -- via the generic ingress, no
YouTube-specific parser.

Recovery-safe (mission section 30): re-running this process against the
SAME production_mission_id resumes from whatever was already persisted
(evidence pack / script / render) rather than redoing completed work or
corrupting the record. Idempotent (mission section 29): the render_id is
deterministic from (production_mission_id, script revision) -- a replay
with the SAME script revision does not create a duplicate render; a NEW
script revision is required for a new render.

Subprocess in the F8 three-process pipeline (mission section 24).
"""

import json
import os
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
YOUTUBE_ROOT = str(Path(FEDERATION_ROOT).parent / "youtube_production")

for _p in (FEDERATION_ROOT, YOUTUBE_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from kernel import FederationKernel

from storage import YouTubeProductionStore, media_output_dir
from schema import (
    EvidencePack, EvidenceItem, Script, ScriptSegment, RenderRecord,
    ThumbnailCandidate, VideoMetadata, ProductionTerminalState,
)
from evidence_pack import build_evidence_pack, build_claim_ledger
from script import generate_script, anti_hallucination_check, fact_check_script
from rights import make_generated_asset_rights, enforce_rights
from media import generate_voice, generate_visual_still, render_video, generate_thumbnail
from metadata import generate_metadata
from qc import run_editorial_qc
from institutional_report import build_youtube_report
from resource_accounting import ResourceMeter


def _to_evidence_pack(d: dict) -> EvidencePack:
    items = [EvidenceItem(**i) for i in d["items"]]
    d2 = dict(d)
    d2["items"] = items
    return EvidencePack(**d2)


def _to_script(d: dict) -> Script:
    segs = [ScriptSegment(**s) for s in d["segments"]]
    d2 = dict(d)
    d2["segments"] = segs
    return Script(**d2)


def run():
    meter = ResourceMeter().start()
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    youtube_db_path = os.environ.get("YOUTUBE_DB_PATH")
    production_mission_id = os.environ.get("PRODUCTION_MISSION_ID")
    run_tag = os.environ.get("F8_RUN_TAG", production_mission_id)
    if not store_path or not youtube_db_path or not production_mission_id:
        raise ValueError("FEDERATION_STORE_PATH, YOUTUBE_DB_PATH, PRODUCTION_MISSION_ID required")

    store = FederationStore(store_path)
    kernel = FederationKernel(store)
    yt_store = YouTubeProductionStore(youtube_db_path)

    mission_row = yt_store.find_mission(production_mission_id)
    if mission_row is None:
        raise RuntimeError(f"no mission {production_mission_id} found -- run process_a first")
    contract = json.loads(mission_row["contract_json"])
    if contract.get("terminal_state") == ProductionTerminalState.NO_APPROPRIATE_CHANNEL.value:
        raise RuntimeError("mission has NO_APPROPRIATE_CHANNEL -- Process B must not be run against it")

    # ---- Evidence pack (recovery: reuse if already built) --------------
    existing_pack = yt_store.find_evidence_pack(production_mission_id)
    if existing_pack:
        pack = _to_evidence_pack(existing_pack)
        pack_reused = True
    else:
        source_event_ref = os.environ.get("SOURCE_EVENT_REF", contract.get("parent_trigger_id", "UNKNOWN"))
        pack = build_evidence_pack(
            production_mission_id=production_mission_id,
            source_event_ref=source_event_ref,
            nexus_synthesis_ref=contract.get("parent_synthesis_id", "UNKNOWN"),
            supporting_findings=json.loads(os.environ.get("SUPPORTING_FINDINGS_JSON", "[]")),
            contradictory_findings=json.loads(os.environ.get("CONTRADICTORY_FINDINGS_JSON", "[]")),
            uncertainties=json.loads(os.environ.get("UNCERTAINTIES_JSON", "[]")),
            temporal_mismatches=json.loads(os.environ.get("TEMPORAL_MISMATCHES_JSON", "[]")),
            specialist_report_ids=json.loads(os.environ.get("SPECIALIST_REPORT_IDS_JSON", "[]")),
        )
        yt_store.save_evidence_pack(pack)
        pack_reused = False

    # ---- Script (recovery: reuse latest revision if already built) -----
    existing_script = yt_store.find_latest_script(production_mission_id)
    if existing_script:
        script = _to_script(existing_script)
        script_reused = True
    else:
        script = generate_script(pack, contract["editorial_objective"])
        yt_store.save_script(script)
        script_reused = False

    if os.environ.get("F8_STOP_AFTER_SCRIPT") == "1":
        # Mission section 30 (recovery) test hook: simulates a real
        # crash immediately after evidence pack + script are persisted,
        # before fact-check/media/render -- a fresh, later invocation of
        # this SAME script (without this env var) must resume from here,
        # not rebuild the pack/script or corrupt the record.
        store.commit()
        print(json.dumps({
            "pid": os.getpid(), "stopped_after_script": True,
            "pack_reused": pack_reused, "script_reused": script_reused,
            "production_mission_id": production_mission_id,
        }, indent=2))
        return 0

    claim_ledger = build_claim_ledger(pack, script)
    yt_store.save_claim_ledger(production_mission_id, claim_ledger)
    claim_ledger_dicts = yt_store.find_claim_ledger(production_mission_id)

    # ---- Anti-hallucination + fact-check --------------------------------
    hallucination_violations = anti_hallucination_check(script, pack)
    fact_check_results, revised_script = fact_check_script(script, claim_ledger_dicts, pack)
    if revised_script.segments != script.segments:
        revised_script.revision = script.revision + 1
        yt_store.save_script(revised_script)
    script = revised_script
    yt_store.save_fact_check_results(production_mission_id, fact_check_results)
    yt_store.increment_counter("scripts_created")
    yt_store.increment_counter("claims_rejected", by=sum(1 for r in fact_check_results if r.outcome == "UNSUPPORTED"))
    yt_store.increment_counter("fact_check_failures", by=sum(1 for r in fact_check_results if r.outcome in ("UNSUPPORTED", "CONTRADICTORY")))

    # ---- Media output directory (external-first) -----------------------
    media_root, is_external = media_output_dir()
    run_dir = media_root / f"f8_{run_tag}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # ---- Voice (real macOS `say`) ---------------------------------------
    narration_text = script.full_text()
    audio_path = run_dir / "narration.aiff"
    audio_path, voice_meta = generate_voice(narration_text, audio_path)
    voice_rights = make_generated_asset_rights(f"{production_mission_id}:voice", "macos_say", narration_text[:200])
    yt_store.save_rights_record(production_mission_id, voice_rights)

    # ---- Visual (real Pillow still) -------------------------------------
    fact_texts = [s.text for s in script.segments if s.segment_class in ("FACT", "ANALYSIS")]
    visual_text = fact_texts[0] if fact_texts else script.segments[0].text
    still_path = run_dir / "still.png"
    generate_visual_still(visual_text, still_path)
    visual_rights = make_generated_asset_rights(f"{production_mission_id}:visual", "pillow", visual_text[:200])
    yt_store.save_rights_record(production_mission_id, visual_rights)

    rights_records_dicts = yt_store.find_rights_records(production_mission_id)
    from schema import RightsRecord
    all_rights = [RightsRecord(**r) for r in rights_records_dicts]
    usable_rights, blocked_rights = enforce_rights(all_rights)

    # ---- Render (real ffmpeg, idempotent by script revision) -----------
    render_id = str(uuid5(NAMESPACE_URL, f"f8-render:{production_mission_id}:rev{script.revision}"))
    existing_render = yt_store.find_latest_render(production_mission_id)
    if existing_render and existing_render.get("render_id") == render_id:
        render_record_dict = existing_render
        render_newly_created = False
    else:
        out_path = run_dir / f"render_rev{script.revision}.mp4"
        script_hash = str(uuid5(NAMESPACE_URL, script.full_text()))
        render_record = render_video(audio_path=audio_path, still_paths=[still_path], out_path=out_path)
        render_record.render_id = render_id
        render_record.production_mission_id = production_mission_id
        render_record.input_script_hash = script_hash
        render_record.revision = script.revision
        render_newly_created = yt_store.save_render_record(render_record)
        render_record_dict = render_record.__dict__
        yt_store.increment_counter("renders_started")
        yt_store.increment_counter("renders_completed")

    render_record_obj = RenderRecord(**render_record_dict) if not isinstance(render_record_dict, RenderRecord) else render_record_dict

    # ---- Thumbnail --------------------------------------------------------
    thumb_text = script.segments[0].text if script.segments else contract["editorial_objective"]
    thumb_path = run_dir / "thumbnail.png"
    generate_thumbnail(thumb_text, thumb_path)
    import hashlib
    thumb_hash = hashlib.sha256(thumb_path.read_bytes()).hexdigest()
    thumbnail = ThumbnailCandidate(
        thumbnail_id=str(uuid5(NAMESPACE_URL, f"f8-thumb:{production_mission_id}:rev{script.revision}")),
        production_mission_id=production_mission_id,
        asset_refs=[f"{production_mission_id}:visual"],
        text=thumb_text,
        claims=[thumb_text],
        evidence_refs=[i.evidence_id for i in pack.items[:1]],
        output_hash=thumb_hash,
        output_path=str(thumb_path),
        rights_status=visual_rights.rights_status,
    )
    yt_store.save_thumbnail(thumbnail)

    # ---- Metadata -----------------------------------------------------------
    executive_conclusion_class = os.environ.get("EXECUTIVE_CONCLUSION_CLASS", "UNKNOWN")
    video_metadata = generate_metadata(script=script, evidence_pack=pack, executive_conclusion_class=executive_conclusion_class)
    yt_store.save_metadata(production_mission_id, video_metadata)

    # ---- Editorial QC -----------------------------------------------------
    qc_result = run_editorial_qc(
        fact_check_results=fact_check_results, script=script, render_record=render_record_obj,
        thumbnail=thumbnail, metadata=video_metadata, blocked_rights=blocked_rights,
    )

    resource_usage_raw = meter.stop()
    external_bytes = render_record_obj.storage_bytes if is_external else 0
    local_bytes = 0 if is_external else render_record_obj.storage_bytes

    # ---- InstitutionalReport, ingested through the generic kernel --------
    report_dict = build_youtube_report(
        mission_id=contract.get("parent_trigger_id", "UNKNOWN") or "UNKNOWN",
        production_mission_id=production_mission_id,
        terminal_state=ProductionTerminalState.READY_FOR_PUBLICATION_AUTHORIZATION.value,
        evidence_pack=pack,
        script=script,
        fact_check_results=fact_check_results,
        render_record=render_record_obj,
        thumbnail=thumbnail,
        metadata=video_metadata,
        rights_usable=usable_rights,
        rights_blocked=blocked_rights,
        qc_result=qc_result,
        resource_usage={
            "cpu_seconds": resource_usage_raw["cpu_seconds"],
            "elapsed_seconds": resource_usage_raw["elapsed_seconds"],
            "peak_memory_bytes": resource_usage_raw["peak_rss_bytes"],
            "api_cost_usd": resource_usage_raw["api_cost_usd"],
            "model_tokens": resource_usage_raw["model_tokens"],
        },
        storage_usage={
            "local_bytes": local_bytes,
            "external_bytes": external_bytes,
            "external_dependency": is_external,
        },
    )
    ingress_result = kernel.ingest_report(raw_payload=report_dict)
    yt_store.save_report(production_mission_id, report_dict["cycle_id"], report_dict, report_dict["timestamp"])

    yt_store.set_terminal_state(
        production_mission_id, ProductionTerminalState.READY_FOR_PUBLICATION_AUTHORIZATION.value, report_dict["timestamp"],
    )
    store.commit()

    result = {
        "pid": os.getpid(),
        "production_mission_id": production_mission_id,
        "pack_reused": pack_reused,
        "script_reused": script_reused,
        "script_revision": script.revision,
        "hallucination_violations": hallucination_violations,
        "fact_check_summary": {
            "total": len(fact_check_results),
            "unsupported_removed": sum(1 for r in fact_check_results if r.outcome == "UNSUPPORTED"),
        },
        "rights": {"usable": len(usable_rights), "blocked": len(blocked_rights)},
        "render_id": render_record_obj.render_id,
        "render_newly_created": render_newly_created,
        "output_hash": render_record_obj.output_hash,
        "output_path": render_record_obj.output_path,
        "duration_seconds": render_record_obj.duration_seconds,
        "storage_is_external": is_external,
        "qc_result": qc_result.__dict__,
        "report_cycle_id": report_dict["cycle_id"],
        "ingress_accepted": ingress_result.accepted,
        "ingress_reason": ingress_result.reason,
        "terminal_state": ProductionTerminalState.READY_FOR_PUBLICATION_AUTHORIZATION.value,
        "resource_usage": resource_usage_raw,
        "federation_store_path": store_path,
        "youtube_db_path": youtube_db_path,
    }
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(run())
