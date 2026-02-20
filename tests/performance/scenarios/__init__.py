"""
Locust scenario user classes.

Each module in this package defines one Locust ``HttpUser`` subclass
that models a specific traffic pattern:

- :mod:`.auth_storm` — authentication-heavy load (token verify + re-login)
- :mod:`.mixed` — production-like blend of reads, writes, and auth checks
- :mod:`.task_crud` — full CRUD cycle including deletes

All concrete scenarios inherit from the abstract base classes in
:mod:`.base`, which handle registration, login, and the shared task
pool.
"""
