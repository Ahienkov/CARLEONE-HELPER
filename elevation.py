"""Compatibility shim for older frozen entry points; elevation is optional."""


def ensure_administrator(api=None):
    """Allow normal startup without requesting or checking administrator rights."""
    return True
