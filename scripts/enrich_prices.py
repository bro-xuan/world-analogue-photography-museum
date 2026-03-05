#!/usr/bin/env python3
"""Enrich camera data with pricing information."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pricing.enrich import main

main()
