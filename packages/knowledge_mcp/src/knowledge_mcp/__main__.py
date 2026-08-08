"""Entry point for `python -m knowledge_mcp`."""

from __future__ import annotations

import sys

from knowledge_mcp.mcp_server import main


if __name__ == "__main__":
    sys.exit(main())
