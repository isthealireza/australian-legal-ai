"""Fail-closed errors for the Federal Register contract seam."""


class FederalRegisterError(Exception):
    """Base error for Federal Register contract failures."""


class FederalRegisterRequestError(FederalRegisterError):
    """The caller supplied an invalid bounded request."""


class FederalRegisterResponseError(FederalRegisterError):
    """The official service returned an unusable response."""


class FederalRegisterRedirectError(FederalRegisterResponseError):
    """The official service returned a redirect that was refused."""
