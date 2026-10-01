#!/usr/bin/env python3
"""TypeFlow launcher:  python run.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing_app.app import main

if __name__ == "__main__":
    raise SystemExit(main())
