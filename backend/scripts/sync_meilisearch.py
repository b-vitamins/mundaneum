#!/usr/bin/env python3
"""
Compatibility wrapper for the packaged Meilisearch sync CLI.
"""

import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "app.cli.sync_meilisearch", *sys.argv[1:]]
        )
    )
