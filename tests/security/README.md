# Security Test Map

This repository uses a marker-based security lane:

- Centralized adversarial tests live in `tests/security/`.
- Security-relevant tests that remain service-owned are marked with `@pytest.mark.security`.

## How To Run

- Local security tests: `make test-security`
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

## Security-Marked Tests Outside `tests/security/`

- `tests/cross_service/test_jwt_contract.py`
- `tests/cross_service/test_auth_task_flow.py` (tenant-isolation case)
- `services/tasks/tests/unit/test_auth.py`
- `services/tasks/tests/integration/test_validation.py` (`TestAuthValidation`)
- `services/tasks/tests/integration/test_tasks_crud.py` (IDOR-oriented cases)
- `services/auth/tests/integration/test_auth_api.py` (selected auth-hardening cases)
- `services/auth/tests/unit/test_models.py` (`password_hash` exposure guard)
