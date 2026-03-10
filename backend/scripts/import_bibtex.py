#!/usr/bin/env python3
"""
Compatibility wrapper for the packaged BibTeX import CLI.
"""

import subprocess
import sys


if __name__ == "__main__":
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "app.cli.import_bibtex", *sys.argv[1:]])
    )
