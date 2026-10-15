import json
import os
import time
from pathlib import Path

from backend.app.agents.deadline_calculation.service import DeadlineCalculationService


def test_deadline_rule_catalog_cache_reloads_when_catalog_changes():
    catalog_path = Path(__file__).with_name(".deadline-cache-test-rules.json")
    service = DeadlineCalculationService()
    service.catalog_path = catalog_path
    try:
        catalog_path.write_text(json.dumps({"rules": [{
            "rule_id": "RULE-1",
            "jurisdiction": "TX",
            "disease": "Example disease",
        }]}), encoding="utf-8")
        original = service._load_rule("Example disease", "TX", None)
        assert original["rule_id"] == "RULE-1"

        time.sleep(0.01)
        catalog_path.write_text(json.dumps({"rules": [{
            "rule_id": "RULE-2",
            "jurisdiction": "TX",
            "disease": "Example disease",
        }]}), encoding="utf-8")
        os.utime(catalog_path, ns=(catalog_path.stat().st_atime_ns, catalog_path.stat().st_mtime_ns + 1_000_000))

        updated = service._load_rule("Example disease", "TX", None)
        assert updated["rule_id"] == "RULE-2"
    finally:
        catalog_path.unlink(missing_ok=True)
