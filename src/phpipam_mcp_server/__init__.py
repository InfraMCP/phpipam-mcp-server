"""phpIPAM MCP Server - MCP server for phpIPAM IP address management."""

__version__ = "0.3.0"

# ``main`` is provided lazily via ``__getattr__`` below (to avoid importing the
# MCP stack at package import). Pylint's static check cannot see that, so the
# undefined-all-variable warning for it is a false positive here.
__all__ = ["main"]  # pylint: disable=undefined-all-variable


def __getattr__(name):
    """Lazily expose ``main`` without importing the MCP stack at package import.

    The ``phpipam-mcp-server`` console script resolves ``phpipam_mcp_server:main``,
    which triggers this. Importing ``server`` eagerly would pull in ``mcp`` for
    every consumer of the package - including the CLI and the shared client,
    which deliberately avoid that dependency. Resolving it on attribute access
    keeps ``import phpipam_mcp_server.client`` / ``.cli`` free of ``mcp``.
    """
    if name == "main":
        from .server import main  # noqa: PLC0415 (intentional lazy import)

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
