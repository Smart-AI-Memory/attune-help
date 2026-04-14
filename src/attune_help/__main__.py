"""Allow ``python -m attune_help`` as an alias for the CLI."""

from __future__ import annotations

import sys

from attune_help.cli import main

if __name__ == "__main__":
    sys.exit(main())
