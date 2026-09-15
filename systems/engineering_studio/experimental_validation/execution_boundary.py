from __future__ import annotations

import json
from pathlib import Path


def transition_decision(
    readiness_record: dict,
    runtime_inspection: dict,
) -> dict:

    auth = readiness_record["authorization"]

    if auth == "BLOCKED":
        return {
            "experiment_id":
                readiness_record["experiment_id"],
            "decision":"BLOCKED",
            "registry_mutation_allowed":False,
            "reason":"REQUIRED_GATES_UNRESOLVED"
        }

    if auth == "READY":
        return {
            "experiment_id":
                readiness_record["experiment_id"],
            "decision":"ALREADY_READY",
            "registry_mutation_allowed":False,
            "reason":"CANONICAL_REGISTRY_ALREADY_READY"
        }

    interfaces = runtime_inspection.get(
        "possible_transition_interfaces",
        []
    )

    if not interfaces:
        return {
            "experiment_id":
                readiness_record["experiment_id"],
            "decision":
                "READY_ELIGIBLE",
            "registry_mutation_allowed":False,
            "reason":
                "CANONICAL_TRANSITION_INTERFACE_REQUIRED"
        }

    return {
        "experiment_id":
            readiness_record["experiment_id"],
        "decision":
            "READY_ELIGIBLE_CANONICAL_INTERFACE_DISCOVERED",
        "registry_mutation_allowed":False,
        "candidate_interfaces":interfaces,
        "reason":
            "INTERFACE_REQUIRES_EXPLICIT_CONTRACT_REVIEW"
    }


def freeze_decision(readiness_record: dict) -> dict:

    if readiness_record["authorization"] != "READY":
        return {
            "experiment_id":
                readiness_record["experiment_id"],
            "freeze_authorized":False,
            "reason":"CANONICAL_READY_REQUIRED"
        }

    return {
        "experiment_id":
            readiness_record["experiment_id"],
        "freeze_authorized":True,
        "reason":"CANONICAL_READY"
    }


def execution_decision(
    readiness_record: dict,
    executor: dict | None,
) -> dict:

    if readiness_record["authorization"] != "READY":
        return {
            "experiment_id":
                readiness_record["experiment_id"],
            "execution_authorized":False,
            "reason":"CANONICAL_READY_REQUIRED"
        }

    if not executor:
        return {
            "experiment_id":
                readiness_record["experiment_id"],
            "execution_authorized":False,
            "reason":
                "CANONICAL_EXECUTOR_NOT_COMMISSIONED"
        }

    if executor.get("canonical") is not True:
        return {
            "experiment_id":
                readiness_record["experiment_id"],
            "execution_authorized":False,
            "reason":
                "EXECUTOR_NOT_CANONICALLY_DESIGNATED"
        }

    return {
        "experiment_id":
            readiness_record["experiment_id"],
        "execution_authorized":True,
        "reason":"CANONICAL_READY_AND_EXECUTOR_DESIGNATED"
    }
