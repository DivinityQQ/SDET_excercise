"""
Performance testing package (Locust-based).

Contains Locust user classes, helper utilities, and a CI threshold
checker that together provide load and performance regression testing
for the task-management API.

Traffic flows through the API gateway (port 5000) into the auth and
task microservices — the same path a single-page application or mobile
client would take.  The server-rendered frontend service (BFF) is
**not** exercised; these tests target the JSON API layer only.

Key Concepts Demonstrated:
- Weighted task distribution to model realistic read/write ratios
- Per-user authentication lifecycle (register → login → use token)
- Tagged scenarios so CI can run subsets via ``--tags``
- CSV-based threshold gates for automated pass/fail decisions
"""
