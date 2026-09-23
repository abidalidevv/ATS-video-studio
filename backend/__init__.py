"""
Avatar Storyteller Video Engine - Backend Package
Ensures UTF-8 console output and environment configuration.
"""
import sys

# Ensure UTF-8 console output on Windows to prevent UnicodeEncodeError with emojis/unicode
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
