"""Create the Phase 3 matter evidence vault.

Revision ID: 0007_evidence_vault
Revises: 0006_playbook_framework
Create Date: 2026-08-06
"""

# ruff: noqa: E501

from collections.abc import Sequence

from alembic import op

from legal_ai.db.evidence_schema import (
    casework_evidence_checklist_links,
    casework_evidence_derivations,
    casework_evidence_records,
)

revision: str = "0007_evidence_vault"
down_revision: str | None = "0006_playbook_framework"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    casework_evidence_records.create(bind)
    casework_evidence_derivations.create(bind)
    casework_evidence_checklist_links.create(bind)
    op.execute("""
    CREATE FUNCTION evidence_record_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'evidence records cannot be deleted'; END IF;
      IF OLD.evidence_id IS DISTINCT FROM NEW.evidence_id OR OLD.matter_id IS DISTINCT FROM NEW.matter_id
        OR OLD.artifact_sha256 IS DISTINCT FROM NEW.artifact_sha256 OR OLD.evidence_kind IS DISTINCT FROM NEW.evidence_kind
        OR OLD.evidence_role IS DISTINCT FROM NEW.evidence_role OR OLD.caller_filename IS DISTINCT FROM NEW.caller_filename
        OR OLD.declared_media_type IS DISTINCT FROM NEW.declared_media_type OR OLD.detected_media_type IS DISTINCT FROM NEW.detected_media_type
        OR OLD.expected_byte_size IS DISTINCT FROM NEW.expected_byte_size OR OLD.supplied_unverified_metadata IS DISTINCT FROM NEW.supplied_unverified_metadata
        OR OLD.registered_by IS DISTINCT FROM NEW.registered_by OR OLD.registered_at IS DISTINCT FROM NEW.registered_at
        OR OLD.review_status <> 'UPLOADED' OR NEW.review_status NOT IN ('REVIEW_ACCEPTED','REVIEW_REJECTED')
        OR NEW.row_version <> OLD.row_version + 1
      THEN RAISE EXCEPTION 'invalid immutable evidence transition'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER trg_evidence_records_update BEFORE UPDATE ON casework_evidence_records FOR EACH ROW EXECUTE FUNCTION evidence_record_guard();
    CREATE TRIGGER trg_evidence_records_delete BEFORE DELETE ON casework_evidence_records FOR EACH ROW EXECUTE FUNCTION evidence_record_guard();
    """)
    op.execute("""
    CREATE FUNCTION evidence_record_insert_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE actual_size integer;
    BEGIN
      SELECT byte_size INTO actual_size FROM provenance_artifacts WHERE sha256=NEW.artifact_sha256;
      IF actual_size IS NULL OR actual_size <> NEW.expected_byte_size THEN RAISE EXCEPTION 'evidence size conflicts with artifact'; END IF;
      IF NEW.review_status <> 'UPLOADED' THEN RAISE EXCEPTION 'evidence must be inserted as UPLOADED'; END IF;
      IF NEW.reviewed_by IS NOT NULL OR NEW.reviewed_at IS NOT NULL OR NEW.review_reason IS NOT NULL THEN RAISE EXCEPTION 'review metadata must be null on insert'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER trg_evidence_records_insert BEFORE INSERT ON casework_evidence_records FOR EACH ROW EXECUTE FUNCTION evidence_record_insert_guard();
    """)
    op.execute("""
    CREATE FUNCTION evidence_derivation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE source_role text; derived_role text;
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'evidence derivations are immutable'; END IF;
      SELECT evidence_role INTO source_role FROM casework_evidence_records WHERE matter_id=NEW.matter_id AND evidence_id=NEW.source_evidence_id;
      SELECT evidence_role INTO derived_role FROM casework_evidence_records WHERE matter_id=NEW.matter_id AND evidence_id=NEW.derived_evidence_id;
      IF derived_role <> 'DERIVED' THEN RAISE EXCEPTION 'derivation output must be DERIVED'; END IF;
      IF EXISTS (WITH RECURSIVE ancestry(id) AS (
          SELECT source_evidence_id FROM casework_evidence_derivations WHERE matter_id=NEW.matter_id AND derived_evidence_id=NEW.source_evidence_id
          UNION ALL SELECT d.source_evidence_id FROM casework_evidence_derivations d JOIN ancestry a ON d.derived_evidence_id=a.id WHERE d.matter_id=NEW.matter_id
        ) SELECT 1 FROM ancestry WHERE id=NEW.derived_evidence_id) THEN RAISE EXCEPTION 'derivation cycle'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER trg_evidence_derivations_guard BEFORE INSERT OR UPDATE OR DELETE ON casework_evidence_derivations FOR EACH ROW EXECUTE FUNCTION evidence_derivation_guard();
    """)
    op.execute("""
    CREATE FUNCTION evidence_role_consistency() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE parent_count integer;
    BEGIN
      SELECT count(*) INTO parent_count FROM casework_evidence_derivations WHERE matter_id=NEW.matter_id AND derived_evidence_id=NEW.evidence_id;
      IF (NEW.evidence_role='DERIVED' AND parent_count<>1) OR (NEW.evidence_role='ORIGINAL' AND parent_count<>0) THEN RAISE EXCEPTION 'evidence role and derivation are inconsistent'; END IF;
      RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER trg_evidence_role_consistency AFTER INSERT OR UPDATE ON casework_evidence_records DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION evidence_role_consistency();
    """)
    op.execute("""
    CREATE FUNCTION evidence_checklist_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE pin uuid; definition jsonb;
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'evidence checklist links are immutable'; END IF;
      SELECT assigned_playbook_version_id INTO pin FROM casework_matters WHERE matter_id=NEW.matter_id;
      IF pin IS NULL OR pin<>NEW.playbook_version_id THEN RAISE EXCEPTION 'checklist link does not match authoritative pin'; END IF;
      SELECT definition_json INTO definition FROM playbook_versions WHERE playbook_version_id=NEW.playbook_version_id;
      IF NOT EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(definition->'evidence_checklist','[]'::jsonb)) item WHERE item->>'checklist_item_id'=NEW.checklist_item_id) THEN RAISE EXCEPTION 'checklist item is not in pinned definition'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER trg_evidence_checklist_links_guard BEFORE INSERT OR UPDATE OR DELETE ON casework_evidence_checklist_links FOR EACH ROW EXECUTE FUNCTION evidence_checklist_link_guard();
    """)


def downgrade() -> None:
    op.execute("""
    DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM casework_evidence_records LIMIT 1)
        OR EXISTS (SELECT 1 FROM casework_evidence_derivations LIMIT 1)
        OR EXISTS (SELECT 1 FROM casework_evidence_checklist_links LIMIT 1)
      THEN RAISE EXCEPTION 'refusing to downgrade 0007_evidence_vault: evidence data present'; END IF;
    END $$;
    """)
    for trigger, table in (
        ("trg_evidence_checklist_links_guard", "casework_evidence_checklist_links"),
        ("trg_evidence_role_consistency", "casework_evidence_records"),
        ("trg_evidence_derivations_guard", "casework_evidence_derivations"),
        ("trg_evidence_records_insert", "casework_evidence_records"),
        ("trg_evidence_records_update", "casework_evidence_records"),
        ("trg_evidence_records_delete", "casework_evidence_records"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    for function in (
        "evidence_checklist_link_guard",
        "evidence_role_consistency",
        "evidence_derivation_guard",
        "evidence_record_insert_guard",
        "evidence_record_guard",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}()")
    op.drop_table("casework_evidence_checklist_links")
    op.drop_table("casework_evidence_derivations")
    op.drop_table("casework_evidence_records")
