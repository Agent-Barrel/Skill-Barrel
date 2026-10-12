"""Put the repo root on sys.path so the `step2step` package imports during
tests without an install step."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
