# Security Test Map

This repository uses a directory-based security lane:

- Centralized adversarial tests live in `tests/security/`.

## How To Run

- Local security tests: `make test-security`
- Direct command: `python -m pytest tests/security -v`
- SAST scan: `make sast`

## OWASP-Oriented Coverage

- `test_mass_assignment.py`
  - Insecure Design / object property abuse.
  - Verifies immutable ownership and server-owned fields.
- `test_input_attack_handling.py`
  - Injection-style payload handling.
  - Verifies SQL-like input is treated as data, not executable logic.
- `test_xss_output_encoding.py`
  - Stored XSS output encoding checks in frontend Jinja templates.
- `test_session_security.py`
  - Session cookie hardening checks (`HttpOnly`, `SameSite`, secure defaults in production).

Service-owned verification tests remain in service and cross-service suites.
