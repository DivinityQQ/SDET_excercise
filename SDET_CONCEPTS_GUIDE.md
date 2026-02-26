# SDET Concepts Guide for Beginners

Welcome! This guide explains Software Development Engineer in Test (SDET) concepts in simple terms. We'll cover both concepts used in this repository and other important ones you should know about.

---

## Table of Contents

1. [What is an SDET?](#what-is-an-sdet)
2. [Concepts Used in This Repository](#concepts-used-in-this-repository)
3. [Important Concepts Not Yet in This Repository](#important-concepts-not-yet-in-this-repository)
4. [Testing Best Practices](#testing-best-practices)

---

## What is an SDET?

An **SDET (Software Development Engineer in Test)** is someone who:
- Writes code to test other code (automation)
- Designs testing strategies
- Builds testing frameworks and tools
- Works closely with developers to ensure quality

Think of it like this: If developers build the car, SDETs build the machines that test if the car works safely and reliably.

---

## Concepts Used in This Repository

### 1. **Test Pyramid** 🔺

**What it is:** A strategy for organizing different types of tests.

```
        /\
       /UI\         <- Few UI tests (slow, expensive)
      /----\
     /  API \       <- More API tests (faster, reliable)
    /--------\
   /   UNIT   \     <- Many unit tests (fast, cheap)
  /____________\
```

**In this repo:**
- **Unit tests** (`services/*/tests/unit/`) - Test individual components in isolation
- **API/Integration tests** (`services/*/tests/integration/`) - Test the REST API endpoints
- **UI/E2E tests** (`tests/e2e/`) - Test the full user interface

**Why it matters:** You want mostly fast unit tests, fewer API tests, and only critical UI tests. This keeps testing fast and reliable.

---

### 2. **Test Fixtures**

**What it is:** Reusable setup code that runs before tests to prepare the test environment.

**Simple analogy:** Like setting the table before a dinner party - you don't want to do it separately for each guest.

**In this repo** (`services/auth/tests/conftest.py`):
```python
@pytest.fixture(scope="function")
def client(app):
    """Creates a test client to make HTTP requests"""
    with app.test_client() as test_client:
        yield test_client

@pytest.fixture(scope="function")
def db_session(app):
    """Creates a clean database for each test"""
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()
        db.drop_all()
```

**Why it matters:** Avoids code duplication and ensures each test starts with a clean slate.

---

### 3. **AAA Pattern (Arrange-Act-Assert)**

**What it is:** A way to structure your tests with three clear sections.

**Example from this repo** (`services/tasks/tests/integration/test_tasks_crud.py`):
```python
def test_get_tasks_returns_empty_list_when_no_tasks(self, client, db_session, api_headers):
    # ARRANGE - provided by db_session fixture (clean database)

    # ACT
    response = client.get("/api/tasks", headers=api_headers)

    # ASSERT
    assert response.status_code == 200
    data = response.get_json()
    assert data["tasks"] == []
    assert data["count"] == 0
```

**Why it matters:** Makes tests easy to read and understand - you know exactly what's being tested.

---

### 4. **Page Object Model (POM)**

**What it is:** A design pattern for UI tests where each web page is represented by a class.

**Simple analogy:** Like having a remote control for each device instead of pressing buttons directly on everything.

**In this repo** (`tests/e2e/pages/`):
```python
class TaskListPage(BasePage):
    """Represents the task list page"""

    def navigate(self):
        """Go to the task list page"""
        self.page.goto(f"{self.base_url}/")

    def get_all_task_titles(self):
        """Get all task titles on the page"""
        return self.page.locator('[data-testid="task-title"]').all_text_contents()
```

**Why it matters:**
- If the UI changes, you only update one place (the page object)
- Tests become more readable: `task_page.create_task()` instead of `click("#button").fill("#input")`

---

### 5. **Test Parametrization**

**What it is:** Running the same test with different inputs automatically.

**In this repo** (`services/tasks/tests/integration/test_validation.py`):
```python
@pytest.mark.parametrize("status", ["PENDING", "Pending", "done", "started", "in-progress", "", 123])
def test_create_task_with_invalid_status_returns_400(self, client, db_session, api_headers, status):
    """Test that non-canonical status values are rejected (case-sensitive enum)"""
    response = client.post("/api/tasks", data=json.dumps({
        "title": "Test Task",
        "status": status
    }), headers=api_headers)
    assert response.status_code == 400
```

**Why it matters:** Write one test, test many scenarios. Saves time and ensures thorough testing.

---

### 6. **Mocking**

**What it is:** Replacing real components with fake ones during testing.

**Simple analogy:** Like using a dummy phone in a movie instead of a real one.

**In this repo** (`tests/mocks/test_external_service.py`):
```python
@patch("requests.post")
def test_patch_requests(self, mock_post):
    """Test without actually calling the real API"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message_id": "123"}
    mock_post.return_value = mock_response

    # Now when code calls requests.post(), it gets our fake response
    result = some_function_that_uses_requests()
    assert result["message_id"] == "123"
```

**Why it matters:**
- Don't need real external services (email, payment APIs, etc.)
- Tests run faster
- No costs for calling real APIs
- Can test error scenarios easily

---

### 7. **Test Markers**

**What it is:** Labels for tests that let you run specific groups.

**In this repo** (`pyproject.toml` pytest settings and tests):
```python
@pytest.mark.api
@pytest.mark.smoke
def test_create_task_with_valid_data(...):
    # This test is tagged as both "api" and "smoke"
```

**Running specific groups:**
```bash
pytest -m "smoke"      # Only smoke tests (quick validation)
pytest -m "api"        # Only API tests
pytest -m "ui"         # Only UI tests
```

**Why it matters:** Run only what you need - smoke tests before a demo, all tests before deployment.

---

### 8. **CI/CD (Continuous Integration/Continuous Deployment)**

**What it is:** Automatically running tests whenever code changes.

**Simple analogy:** Like a car's warning light that automatically checks if something's wrong.

**In this repo** (`.github/workflows/pr.yml`, `main.yml`, `pr-nightly.yml`, `release.yml`):
- Every time you open a pull request, push to main, or tag a release
- Automatically runs linting, per-service tests, cross-service tests, smoke tests, and performance gates
- Nightly run executes the full suite including Playwright E2E tests
- If any test fails, you get notified

**Why it matters:**
- Catch bugs immediately
- Don't rely on developers remembering to run tests
- Everyone sees test results

---

### 9. **Boundary Testing**

**What it is:** Testing the limits and edges of acceptable inputs.

**In this repo** (`tests/integration/test_validation.py`):
```python
def test_create_task_title_max_length(self, client):
    """Test maximum allowed title length (200 characters)"""
    title = "A" * 200  # Exactly 200 characters
    response = client.post("/api/tasks", data=json.dumps({"title": title}))
    assert response.status_code == 201  # Should succeed

def test_create_task_title_exceeds_max_length(self, client):
    """Test title that's too long (201 characters)"""
    title = "A" * 201  # Too long!
    response = client.post("/api/tasks", data=json.dumps({"title": title}))
    assert response.status_code == 400  # Should fail
```

**Why it matters:** Bugs often hide at boundaries (max length, zero, negative numbers).

---

### 10. **Negative Testing**

**What it is:** Testing what happens when things go wrong.

**In this repo** (`tests/integration/test_validation.py`):
```python
def test_create_task_missing_required_fields(self, client):
    """What if we don't send a title?"""
    response = client.post("/api/tasks", data=json.dumps({}))
    assert response.status_code == 400  # Should reject it

def test_get_non_existent_task(self, client):
    """What if we ask for a task that doesn't exist?"""
    response = client.get("/api/tasks/999999")
    assert response.status_code == 404  # Should return "not found"
```

**Why it matters:** Your app should handle errors gracefully, not crash.

---

### 11. **Test Isolation**

**What it is:** Each test runs independently and doesn't affect other tests.

**In this repo:**
- Each test gets a fresh database
- Tests can run in any order
- One failing test doesn't break others

**Why it matters:** Flaky tests (tests that randomly fail) are usually caused by tests interfering with each other.

---

### 12. **Test Reporting**

**What it is:** Creating readable reports of test results.

**In this repo:**
- Screenshots when UI/E2E tests fail, saved to `test-results/screenshots/`
- Shows which tests passed/failed and why
- Stored in GitHub Actions artifacts for 30 days

**Why it matters:** When tests fail, you need to quickly understand what went wrong.

---

### 13. **Performance Testing** ⚡

**What it is:** Testing how fast your application is and how much load it can handle.

**Types:**
- **Load Testing:** Can your app handle 1,000 users at once?
- **Stress Testing:** At what point does your app break?
- **Spike Testing:** What if traffic suddenly jumps 10x?
- **Soak Testing:** Does your app leak memory over 24 hours?

**In this repo** (`tests/performance/`):
```python
from locust import HttpUser, task, between

class TaskUser(HttpUser):
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    @task
    def get_tasks(self):
        self.client.get("/api/tasks")

    @task(3)  # This runs 3x more often
    def create_task(self):
        self.client.post("/api/tasks", json={
            "title": "Load test task"
        })
```

Threshold checks run automatically in CI after each Locust scenario and fail the build if latency or error-rate limits are exceeded (`tests/performance/thresholds.yml`).

**Why it matters:** Your app might work with 10 users but crash with 1,000.

---

## Important Concepts Not Yet in This Repository

### 1. **Contract Testing** 🤝

**What it is:** Testing that different services agree on how they communicate.

**Simple analogy:** Like making sure a plug fits the socket before buying an appliance.

**Scenario:**
- You have a frontend that calls a backend API
- Backend says: "I'll send you `{userId: 123, name: "John"}`"
- Frontend expects: `{userId: number, name: string}`
- Contract testing verifies this agreement

**Tools:**
- Pact - Most popular contract testing tool
- Spring Cloud Contract - For Java/Spring apps

**Example (Pact):**
```python
# Consumer (Frontend) defines what it expects
pact.given("user exists").upon_receiving(
    "a request for user details"
).with_request(
    "GET", "/api/users/1"
).will_respond_with(200, body={
    "userId": 1,
    "name": "John"
})

# Provider (Backend) must fulfill this contract
```

**Why it matters:** Prevents "it works on my machine" problems when services integrate.

---

### 3. **Visual Regression Testing** 👁️

**What it is:** Taking screenshots and comparing them to detect unwanted visual changes.

**Simple analogy:** Like a "spot the difference" game - find what changed in the UI.

**Tools:**
- Percy - Cloud-based visual testing
- Applitools - AI-powered visual testing
- BackstopJS - Open-source screenshot comparison
- Playwright has built-in screenshot comparison

**Example (Playwright):**
```python
def test_homepage_visual(page):
    page.goto("http://localhost:5000")
    # First run creates baseline, future runs compare to it
    page.screenshot(path="homepage.png")
    expect(page).to_have_screenshot("homepage.png")
```

**Why it matters:** CSS changes can break layouts in ways functional tests miss.

---

### 4. **Security Testing** 🔒

**What it is:** Testing for vulnerabilities that hackers could exploit.

**Common tests:**
- **SQL Injection:** Can hackers inject malicious database queries?
- **XSS (Cross-Site Scripting):** Can attackers inject malicious JavaScript?
- **Authentication/Authorization:** Can users access things they shouldn't?
- **CSRF (Cross-Site Request Forgery):** Can attackers forge requests?
- **Sensitive Data Exposure:** Are passwords stored securely?

**Tools:**
- OWASP ZAP - Free security testing tool
- Burp Suite - Industry standard for security testing
- Snyk - Finds vulnerabilities in dependencies
- Bandit - Python security linter

**Example test:**
```python
def test_sql_injection_protection(client):
    """Try to inject SQL through the title field"""
    malicious_title = "Test'; DROP TABLE tasks; --"
    response = client.post("/api/tasks", json={"title": malicious_title})

    # Should either reject it or escape it safely
    assert response.status_code in [400, 201]

    # Database should still exist
    tasks = client.get("/api/tasks")
    assert tasks.status_code == 200
```

**Why it matters:** Security bugs can leak user data or allow system takeover.

---

### 5. **Accessibility Testing** ♿

**What it is:** Testing that your app works for people with disabilities.

**What to test:**
- **Screen readers:** Can blind users navigate your app?
- **Keyboard navigation:** Can users without a mouse use your app?
- **Color contrast:** Can color-blind users read text?
- **Alt text:** Do images have descriptions?
- **ARIA labels:** Are interactive elements properly labeled?

**Tools:**
- axe-core - Accessibility testing engine
- Pa11y - Automated accessibility testing
- WAVE - Browser extension for accessibility
- Lighthouse - Chrome DevTools audit tool

**Example (with Playwright and axe):**
```python
from playwright.sync_api import Page
from axe_playwright_python import Axe

def test_homepage_accessibility(page: Page):
    page.goto("http://localhost:5000")
    axe = Axe()
    results = axe.run(page)

    # Should have no violations
    assert len(results.violations) == 0, f"Accessibility violations: {results.violations}"
```

**Why it matters:**
- Legal requirement in many countries
- About 15% of the population has some disability
- Makes your app better for everyone

---

### 6. **Mutation Testing** 🧬

**What it is:** Intentionally breaking your code to see if your tests catch it.

**How it works:**
1. Tool changes your code (e.g., changes `>` to `>=`)
2. Runs your tests
3. If tests still pass, you have a gap in coverage

**Simple analogy:** Like checking if a security guard is awake by sneaking something past them.

**Tools:**
- mutmut - Python mutation testing
- Stryker - JavaScript/TypeScript mutation testing
- PIT - Java mutation testing

**Example:**
```python
# Original code
def is_adult(age):
    return age >= 18

# Mutated code (by tool)
def is_adult(age):
    return age > 18  # Changed >= to >

# If your tests still pass with this mutation, you're missing:
def test_boundary():
    assert is_adult(18) == True  # This test would catch it!
```

**Why it matters:** High code coverage doesn't mean good tests - mutation testing finds weak spots.

---

### 7. **Data-Driven Testing** 📊

**What it is:** Reading test data from external files (CSV, Excel, JSON, databases).

**Simple analogy:** Like having a recipe book instead of remembering every recipe.

**Example:**
```python
# test_data.json
[
    {"username": "user1", "password": "pass1", "should_succeed": true},
    {"username": "user2", "password": "wrong", "should_succeed": false},
    {"username": "user3", "password": "pass3", "should_succeed": true}
]

# test_login.py
import json

def test_login_with_data_file():
    with open("test_data.json") as f:
        test_cases = json.load(f)

    for case in test_cases:
        response = client.post("/login", json={
            "username": case["username"],
            "password": case["password"]
        })

        if case["should_succeed"]:
            assert response.status_code == 200
        else:
            assert response.status_code == 401
```

**Why it matters:**
- Non-programmers can add test cases
- Easy to maintain large test datasets
- Separate test logic from test data

---

### 8. **Test Coverage** 📈

**What it is:** Measuring how much of your code is executed by tests.

**Types:**
- **Line Coverage:** What % of code lines run during tests?
- **Branch Coverage:** What % of if/else branches are tested?
- **Function Coverage:** What % of functions are called?

**Tools:**
- coverage.py - Python coverage tool
- pytest-cov - Pytest integration
- Istanbul - JavaScript coverage
- JaCoCo - Java coverage

**Running coverage (this repo):**
```bash
# Combined local coverage (services + gateway + cross-service)
make test-cov
# Opens htmlcov/index.html

# Per-service coverage (example: auth)
make test-auth-cov
# Opens htmlcov/auth/index.html
```

**Example report:**
```
Name                                             Stmts   Miss  Cover
---------------------------------------------------------------------
services/auth/auth_app/routes/api.py                82      5    94%
services/tasks/task_app/routes/api.py              151     11    93%
services/frontend/frontend_app/routes/views.py     378    250    34%
gateway/gateway_app/routes.py                       73      4    95%
---------------------------------------------------------------------
TOTAL                                               928    287    69%
```

**Why it matters:** Shows untested code, but 100% coverage doesn't guarantee bug-free code!

---

### 9. **Smoke Testing** 🔥

**What it is:** Quick tests of critical functionality to see if the build is stable enough for further testing.

**Simple analogy:** Like checking if your car starts before planning a road trip.

**In this repo:** Already present via `@pytest.mark.smoke` markers!
```python
@pytest.mark.smoke
def test_create_and_view_task(...)  # Critical path test
```

**Typical smoke test scenarios:**
- App starts successfully
- Database connection works
- Login works
- Critical API endpoints respond
- No crashes on homepage

**Why it matters:** No point running 1,000 tests if the app won't even start.

---

### 10. **Exploratory Testing** 🔍

**What it is:** Manual testing where testers actively explore the app without a script.

**Not automated, but important!**

**How it works:**
- Tester uses the app like a real user
- Tries unexpected combinations
- Looks for edge cases
- Reports bugs and UX issues

**Techniques:**
- **Session-based:** Time-boxed testing sessions (2 hours)
- **Charter-based:** Start with a goal ("Test file upload")
- **Freestyle:** Just play with the app

**Why it matters:** Automated tests only check what you programmed them to check. Humans find unexpected issues.

---

### 11. **Test Data Management** 🗃️

**What it is:** Strategies for creating, managing, and cleaning up test data.

**Strategies:**
- **Synthetic data:** Generated data (Faker library - already used in this repo!)
- **Anonymized production data:** Real data with sensitive info removed
- **Fixture files:** Static test data in JSON/YAML files
- **Database snapshots:** Save/restore database states

**In this repo (already present):**
```python
from faker import Faker
fake = Faker()

@pytest.fixture
def task_factory(db_session):
    def create_task(**kwargs):
        defaults = {
            "title": fake.sentence(),
            "description": fake.paragraph(),
            "status": "pending"
        }
        defaults.update(kwargs)
        task = Task(**defaults)
        db_session.add(task)
        db_session.commit()
        return task
    return create_task
```

**Advanced concepts:**
- **Test data versioning:** Keep test data in version control
- **Data masking:** Hide sensitive info in test environments
- **Data subsetting:** Copy only relevant production data

---

### 12. **API Schema Validation** 📋

**What it is:** Validating that API responses match their documented structure.

**Tools:**
- JSON Schema - Standard for validating JSON
- OpenAPI/Swagger - API documentation + validation
- Pydantic - Python data validation

**Example:**
```python
# Define expected schema
task_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "title": {"type": "string"},
        "status": {"enum": ["pending", "in_progress", "completed"]},
        "created_at": {"type": "string", "format": "date-time"}
    },
    "required": ["id", "title", "status"]
}

# Validate response
from jsonschema import validate

def test_create_task_response_schema(client):
    response = client.post("/api/tasks", json={"title": "Test"})
    validate(instance=response.json(), schema=task_schema)  # Will raise error if invalid
```

**Why it matters:** Ensures API consistency and catches breaking changes early.

---

### 13. **Chaos Engineering** 💥

**What it is:** Intentionally breaking your system to test its resilience.

**What you test:**
- What if the database goes down?
- What if network latency is 5 seconds?
- What if a service uses 100% CPU?
- What if disk space runs out?

**Tools:**
- Chaos Monkey - Netflix's famous chaos tool
- Gremlin - Chaos engineering platform
- Pumba - Docker chaos testing
- Chaos Toolkit - Open-source chaos engineering

**Example scenario:**
```python
# Simulate database connection failure
@patch("app.db.session.commit")
def test_graceful_degradation(mock_commit):
    mock_commit.side_effect = ConnectionError("Database unavailable")

    response = client.post("/api/tasks", json={"title": "Test"})

    # Should return 503 Service Unavailable, not 500 Internal Error
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["message"].lower()
```

**Why it matters:** Real systems fail - test that your app handles failures gracefully.

---

### 14. **Test Environments** 🌍

**What it is:** Different setups where tests run (local, staging, production-like).

**Common environments:**

```
Developer Machine → Dev Environment → QA Environment → Staging → Production
     (unit tests)     (integration)      (full suite)     (smoke)   (monitoring)
```

**Characteristics:**
- **Local:** Fast feedback, isolated
- **Dev:** Shared, frequently updated
- **QA:** Stable, full test suite
- **Staging:** Production-like, final validation
- **Production:** Real users, monitoring only

**Configuration (this repo uses this approach):**
```python
# config.py
class DevelopmentConfig(Config):
    DEBUG = True
    DATABASE_URI = "sqlite:///dev.db"

class TestingConfig(Config):
    TESTING = True
    DATABASE_URI = "sqlite:///test.db"

class ProductionConfig(Config):
    DEBUG = False
    DATABASE_URI = os.environ.get("DATABASE_URL")
```

**Why it matters:** Catch environment-specific bugs before production.

---

### 15. **Continuous Testing** ♾️

**What it is:** Running tests continuously throughout development, not just at the end.

**When tests run:**
- On file save (watch mode)
- On git commit (pre-commit hooks)
- On pull request (this repo has this!)
- On merge to main (this repo has this!)
- Periodically (e.g., nightly builds)

**Tools:**
- pytest-watch - Reruns tests when files change
- pre-commit - Git hooks for running tests
- GitHub Actions - Already in this repo!

**Example (watch mode):**
```bash
# Install pytest-watch
pip install pytest-watch

# Runs tests automatically when you save files
ptw tests/
```

**Why it matters:** Catch bugs immediately instead of at the end of the sprint.

---

## Testing Best Practices

### 1. **Write Tests First (TDD - Test-Driven Development)**

**Process:**
1. Write a failing test
2. Write minimal code to pass
3. Refactor
4. Repeat

**Benefits:**
- Forces you to think about requirements
- Ensures code is testable
- High test coverage naturally

---

### 2. **Keep Tests Fast** ⚡

**How:**
- Use mocks instead of real services
- Run unit tests most often (they're fastest)
- Parallelize test execution
- Use in-memory databases when possible

**Slow test = test that won't be run**

---

### 3. **Make Tests Independent**

Each test should:
- Set up its own data
- Clean up after itself
- Work in any order
- Not depend on other tests

---

### 4. **Test One Thing Per Test**

**Bad:**
```python
def test_everything():
    # Create task
    # Update task
    # Delete task
    # Create another task
    # Filter tasks
    # ... (too much!)
```

**Good:**
```python
def test_create_task():
    # Only tests task creation

def test_update_task():
    # Only tests task updating
```

---

### 5. **Use Descriptive Test Names**

**Bad:** `test_task()`, `test_1()`, `test_error()`

**Good:**
- `test_create_task_with_valid_data_returns_201()`
- `test_create_task_without_title_returns_400()`
- `test_delete_non_existent_task_returns_404()`

**You should understand what failed just from the test name.**

---

### 6. **Test the Right Things**

**Do test:**
- Business logic
- Edge cases and boundaries
- Error handling
- Critical user flows

**Don't test:**
- Framework code (trust that Flask works)
- Getters/setters without logic
- Obvious code

---

### 7. **Maintain Tests Like Production Code**

- Refactor duplicate test code
- Use fixtures and helper functions
- Keep tests readable
- Update tests when requirements change

**Tests are code too!**

---

## Quick Reference: When to Use What

| Testing Type | When to Use | Example |
|--------------|-------------|---------|
| **Unit Tests** | Testing individual functions/methods | "Does this function calculate the total correctly?" |
| **API Tests** | Testing endpoints and business logic | "Does POST /api/tasks create a task?" |
| **UI/E2E Tests** | Testing critical user workflows | "Can a user create and edit a task?" |
| **Mock Tests** | Isolating code from external dependencies | "Test email sending without actual email service" |
| **Performance Tests** | Ensuring app handles load | "Can we handle 1000 concurrent users?" |
| **Security Tests** | Finding vulnerabilities | "Can users access other users' tasks?" |
| **Visual Tests** | Detecting UI changes | "Did this CSS change break the layout?" |
| **Smoke Tests** | Quick validation before full testing | "Does the app start and is the homepage working?" |

---

## Learning Path Recommendation

If you're new to testing, learn in this order:

1. **Unit Testing Basics** ✅ (this repo has examples)
   - AAA pattern
   - Fixtures
   - Assertions

2. **API Testing** ✅ (this repo has examples)
   - HTTP methods
   - Status codes
   - Response validation

3. **Mocking** ✅ (this repo has examples)
   - When to mock
   - unittest.mock basics

4. **UI Testing** ✅ (this repo has examples)
   - Page Object Model
   - Playwright basics

5. **CI/CD** ✅ (this repo has examples)
   - GitHub Actions
   - Automated testing

6. **Performance Testing** ✅ (this repo has examples)
   - Locust load scenarios
   - Threshold-based pass/fail gates

7. **Test Coverage** (add this next!)
   - Running coverage reports
   - Interpreting results

8. **Security Testing** (intermediate)
   - Common vulnerabilities
   - OWASP Top 10

9. **Advanced Concepts** (advanced)
   - Contract testing
   - Chaos engineering
   - Mutation testing

---

## Resources

### Books
- "Test Driven Development: By Example" by Kent Beck
- "The Art of Software Testing" by Glenford Myers
- "Continuous Delivery" by Jez Humble

### Online
- Playwright Documentation: https://playwright.dev
- Pytest Documentation: https://docs.pytest.org
- Test Automation University: https://testautomationu.applitools.com

### Practice
- This repository - try adding new tests!
- HackerRank - coding challenges
- Test automation practice sites (e.g., demo.playwright.dev)

---

## Summary

**SDET work is about:**
1. **Writing code** to test code (automation)
2. **Preventing bugs** before they reach production
3. **Building confidence** that changes won't break things
4. **Making testing faster** and more reliable
5. **Ensuring quality** throughout development

**This repository demonstrates:**
- Test Pyramid (unit/API/UI tests)
- Test automation with Pytest and Playwright
- Page Object Model
- CI/CD with GitHub Actions
- Test fixtures and isolation
- Mocking external dependencies
- Test organization and markers

**You should explore next:**
- Test coverage analysis
- Performance testing
- Security testing
- Visual regression testing
- Contract testing

Remember: **Good tests give you confidence to change code without fear!** 🚀

---

Happy Testing! If you have questions about any concept, feel free to ask or explore the code in this repository.
