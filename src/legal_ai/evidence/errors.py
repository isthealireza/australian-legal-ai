"""Typed fail-closed errors for the evidence boundary."""


class EvidenceError(Exception):
    """Base class for evidence boundary failures."""


class EvidenceNotFound(EvidenceError):
    pass


class UnsafeFilename(EvidenceError):
    pass


class UnsupportedFileType(EvidenceError):
    pass


class MalformedSignature(EvidenceError):
    pass


class DeclaredMediaTypeMismatch(EvidenceError):
    pass


class ExtensionMismatch(EvidenceError):
    pass


class EmptyEvidenceInput(EvidenceError):
    pass


class EvidenceSizeLimitExceeded(EvidenceError):
    pass


class ExpectedSizeMismatch(EvidenceError):
    pass


class TruncatedEvidenceStream(EvidenceError):
    pass


class ClosedMatterEvidenceWriteDenied(EvidenceError):
    pass


class EvidenceAuthorityDenied(EvidenceError):
    pass


class CrossMatterEvidenceDenied(EvidenceError):
    pass


class EvidenceProvenanceConflict(EvidenceError):
    pass


class InvalidReviewTransition(EvidenceError):
    pass


class MissingDerivationSource(EvidenceError):
    pass


class SameContentDerivation(EvidenceError):
    pass


class DerivationCycle(EvidenceError):
    pass


class InvalidChecklistAssociation(EvidenceError):
    pass


class EvidenceAuditWriteFailed(EvidenceError):
    pass


class EvidenceStorageFailure(EvidenceError):
    pass


class ImmutableEvidenceMutation(EvidenceError):
    pass


class TerminalReviewMutationDenied(EvidenceError):
    pass


class ChecklistLinkConflict(EvidenceError):
    pass


class ChecklistLinkPersistenceError(EvidenceError):
    pass
