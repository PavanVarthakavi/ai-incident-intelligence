"""Read-only HTTP clients for observability backends.

Each client hides one vendor's API format and returns typed values. Any failure
(network, timeout, HTTP error, malformed response) is raised as ``BackendError``
so callers handle a single exception type.
"""
