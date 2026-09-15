#!/usr/bin/env python3
"""NEWS PROCESS: real RSS acquisition -> normalization -> dedup ->
entity extraction -> event construction -> InstitutionalReport ->
persisted to the federation store (via the SAME generic kernel ingress
DAT.AI/Librarian/Sentinel already use).

Subprocess 1 of the F7 event-driven cognitive loop (mission section 25).
No user-authored trigger after this point -- everything downstream
(NEXUS relevance, specialist delegation, synthesis) is driven entirely
by what this process acquires and reports.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

NEWS_ROOT = str(Path(__file__).resolve().parents[4] / "news_intelligence")
FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")

for _p in (NEWS_ROOT, FEDERATION_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from kernel import FederationKernel

from acquisition import SOURCE_REGISTRY, fetch_source
from entity_resolution import clean_text_for_extraction, extract_entities
from event_engine import build_event
from storage import NewsStore
from institutional_report import build_news_report

NEWS_DB_DEFAULT = str(Path(NEWS_ROOT) / "runtime" / "news_intelligence.db")


def run():
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    news_db_path = os.environ.get("NEWS_DB_PATH", NEWS_DB_DEFAULT)
    headline_filter = os.environ.get("F7_HEADLINE_FILTER")  # e.g. 'Samsung' -- selects which real acquired item to build an event from
    if not store_path:
        raise ValueError("FEDERATION_STORE_PATH environment variable required")

    store = FederationStore(store_path)
    kernel = FederationKernel(store)
    news_store = NewsStore(news_db_path)

    now = datetime.now(timezone.utc)
    acquisition_run_id = str(uuid4())

    all_items = []
    health_summaries = []
    source_failures = 0

    for config in SOURCE_REGISTRY:
        items, health = fetch_source(config)
        news_store.log_source_health(health, now.isoformat())
        health_summaries.append({
            "source_id": health.source_id, "status": health.status.value,
            "item_yield": health.item_yield, "http_status": health.http_status,
        })
        if health.status.value == "UNAVAILABLE":
            source_failures += 1
        all_items.extend(items)

    items_accepted = 0
    duplicates = 0
    for item in all_items:
        existing = news_store.find_existing_source_item(item.source_item_id)
        if existing and existing["content_hash"] == item.content_hash:
            duplicates += 1
            continue
        news_store.store_source_item(item, is_update=bool(existing))
        items_accepted += 1

    # Select the real item this run builds an event from.
    if headline_filter:
        candidates = [i for i in all_items if headline_filter in i.headline]
    else:
        candidates = all_items
    if not candidates:
        raise RuntimeError(f"no acquired item matched filter {headline_filter!r}")
    target_item = candidates[0]

    text = target_item.headline + " " + clean_text_for_extraction(target_item.raw_description)
    entities = extract_entities(text)

    existing_events = news_store.all_events()
    event = build_event(items=[target_item], entities=entities, existing_events=existing_events)
    news_store.store_event(event)

    report_dict, event_metadata = build_news_report(
        mission_id=str(uuid4()), event=event, source_health_summaries=health_summaries,
    )

    ingress_result = kernel.ingest_report(raw_payload=report_dict, now=now)

    store.commit()

    result = {
        "pid": os.getpid(),
        "acquisition_run_id": acquisition_run_id,
        "items_fetched": len(all_items),
        "items_accepted": items_accepted,
        "duplicates": duplicates,
        "source_failures": source_failures,
        "source_health": health_summaries,
        "target_headline": target_item.headline,
        "target_source_item_id": target_item.source_item_id,
        "event_id": event.event_id,
        "event_metadata": event_metadata,
        "report_cycle_id": report_dict["cycle_id"],
        "ingress_accepted": ingress_result.accepted,
        "ingress_reason": ingress_result.reason,
        "provenance_ids": ingress_result.provenance_ids,
        "federation_store_path": store_path,
        "news_db_path": news_db_path,
    }
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(run())
