from legal_ai.evidence.service import EvidenceService


def test_service_exposes_no_delete_or_mutation_surface() -> None:
    public = {name for name in dir(EvidenceService) if not name.startswith("_")}
    assert "delete" not in public
    assert "update" not in public
    assert {"upload", "register_derived", "review", "link_checklist", "read", "ancestry"} <= public
