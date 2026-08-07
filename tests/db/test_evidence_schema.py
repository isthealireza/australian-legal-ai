from legal_ai.db.evidence_schema import EVIDENCE_TABLES, casework_evidence_records


def test_evidence_tables_share_authoritative_metadata() -> None:
    assert [table.name for table in EVIDENCE_TABLES] == [
        "casework_evidence_records",
        "casework_evidence_derivations",
        "casework_evidence_checklist_links",
    ]
    assert {"matter_id", "artifact_sha256", "review_status", "row_version"} <= set(
        casework_evidence_records.c.keys()
    )
