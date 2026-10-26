"""Main entrypoint for PromptProbe module execution via python -m promptprobe."""

import sys

from promptprobe.cli import main

if __name__ == "__main__":
    sys.exit(main())
