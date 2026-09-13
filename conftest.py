"""Root pytest config.

scripts/ holds MANUAL diagnostics (run via `python scripts/...`),
never part of the suite — ignore them at collection time.
"""

collect_ignore = [
    "scripts/test_ai_connection.py",
    "scripts/test_structured_output.py",
    "scripts/benchmark_ai.py",
]
