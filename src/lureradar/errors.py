"""Exception hierarchy. Every error LureRadar raises on purpose is a LureRadarError."""

from __future__ import annotations


class LureRadarError(Exception):
    """Base class for expected, user-facing errors."""


class InvalidTargetError(LureRadarError):
    """The input could not be parsed as a URL, domain or text."""


class PackError(LureRadarError):
    """A campaign pack is missing or invalid."""


class FetchBlockedError(LureRadarError):
    """The hardened fetcher refused a request (SSRF guard, content type, size...)."""


class SourceError(LureRadarError):
    """A data source failed or returned unusable data."""


class SignatureError(LureRadarError):
    """A detached feed signature failed to verify."""


class FeedError(LureRadarError):
    """A feed document is malformed or fails validation."""
