import hashlib
import json
import tempfile
from pathlib import Path

from experimental_validation.gate_validator import validate_gate_record

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical():
    return {
        "gate_id": "test-gate-01",
        "canonical_gate_text": "exact canonical requirement",
    }

def save(path, data):
    path.write_text(json.dumps(data))

def valid_record(evidence):
    return {
        "gate_id": "test-gate-01",
        "gate": "exact canonical requirement",
        "status": "PASS",
        "reviewer": "independent-reviewer-001",
        "verified_at": "2026-09-14T00:00:00Z",
        "contradictions_resolved": True,
        "evidence_refs": [{
            "path": str(evidence.resolve()),
            "sha256": digest(evidence),
        }],
    }

def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        evidence = root / "evidence.txt"
        evidence.write_text("verification evidence\n")

        p = root / "valid.json"
        save(p, valid_record(evidence))
        assert validate_gate_record(p, canonical())["valid"]

        r = valid_record(evidence)
        r["gate"] = "wrong"
        p = root / "wrong_gate.json"
        save(p, r)
        result = validate_gate_record(p, canonical())
        assert not result["valid"]
        assert "EXACT_GATE_TEXT_MISMATCH" in result["reasons"]

        r = valid_record(evidence)
        r["reviewer"] = ""
        p = root / "missing_reviewer.json"
        save(p, r)
        result = validate_gate_record(p, canonical())
        assert not result["valid"]
        assert "REVIEWER_MISSING" in result["reasons"]

        r = valid_record(evidence)
        r["evidence_refs"][0]["path"] = str(root / "missing.txt")
        p = root / "missing_evidence.json"
        save(p, r)
        result = validate_gate_record(p, canonical())
        assert not result["valid"]
        assert any(x.startswith("EVIDENCE_FILE_MISSING") for x in result["reasons"])

        r = valid_record(evidence)
        r["evidence_refs"][0]["sha256"] = "0" * 64
        p = root / "bad_hash.json"
        save(p, r)
        result = validate_gate_record(p, canonical())
        assert not result["valid"]
        assert any(x.startswith("EVIDENCE_HASH_MISMATCH") for x in result["reasons"])

        r = valid_record(evidence)
        r["contradictions_resolved"] = False
        p = root / "contradiction.json"
        save(p, r)
        result = validate_gate_record(p, canonical())
        assert not result["valid"]
        assert "CONTRADICTIONS_NOT_RESOLVED" in result["reasons"]

    print("PASS: strict gate validator adversarial tests")

if __name__ == "__main__":
    main()
