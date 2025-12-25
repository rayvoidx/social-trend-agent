# Testing Guide - Social Trend Agent

**Last Updated:** 2025-12-25

This guide covers all testing workflows for the social-trend-agent project.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Backend Testing (Pytest)](#backend-testing-pytest)
3. [Frontend Testing (Cypress)](#frontend-testing-cypress)
4. [Coverage Reports](#coverage-reports)
5. [CI/CD Integration](#cicd-integration)

---

## Quick Start

### Install Dependencies

**Backend:**
```bash
pip install -r requirements.txt
# Includes: pytest, pytest-asyncio, pytest-cov, pytest-mock
```

**Frontend:**
```bash
cd apps/web
npm install
npm install --save-dev cypress @cypress/vite-dev-server
```

### Run All Tests

**Backend:**
```bash
pytest
```

**Frontend:**
```bash
cd apps/web
npm run test:e2e
```

---

## Backend Testing (Pytest)

### Test Structure

```
tests/
├── unit/                           # Fast, isolated tests
│   ├── infrastructure/
│   │   ├── test_cache.py          # SimpleCache, DiskCache
│   │   └── test_async_redis_cache.py  # AsyncRedisCache
│   ├── core/                       # Core logic tests
│   └── agents/                     # Agent unit tests
├── integration/                    # Slower, service-dependent tests
│   ├── test_api_server.py         # API endpoint tests
│   ├── test_news_agent_integration.py
│   └── test_social_trend_agent.py
└── __init__.py
```

### Running Tests

**All tests with coverage:**
```bash
pytest
```

**Unit tests only (fast):**
```bash
pytest -m unit
```

**Integration tests only:**
```bash
pytest -m integration
```

**Specific file:**
```bash
pytest tests/unit/infrastructure/test_cache.py
```

**Specific test:**
```bash
pytest tests/unit/infrastructure/test_cache.py::TestSimpleCache::test_set_and_get
```

**Verbose output:**
```bash
pytest -v
```

**Stop on first failure:**
```bash
pytest -x
```

**Show print statements:**
```bash
pytest -s
```

**Parallel execution (faster):**
```bash
# Install pytest-xdist first: pip install pytest-xdist
pytest -n auto
```

### Test Markers

**Available markers:**
- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Integration tests requiring services
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.asyncio` - Async tests

**Example:**
```python
import pytest

@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_cache():
    # Test code
    pass
```

**Run by marker:**
```bash
pytest -m unit
pytest -m "not slow"
pytest -m "unit and asyncio"
```

### Writing Tests

**Unit Test Example:**
```python
# tests/unit/infrastructure/test_my_module.py

import pytest

class TestMyClass:
    """Test suite for MyClass."""

    @pytest.fixture
    def my_instance(self):
        """Create instance for testing."""
        return MyClass(param="test")

    def test_basic_functionality(self, my_instance):
        """Test basic functionality."""
        result = my_instance.do_something()
        assert result == "expected"

    def test_error_handling(self, my_instance):
        """Test error cases."""
        with pytest.raises(ValueError):
            my_instance.invalid_operation()
```

**Async Test Example:**
```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await my_async_function()
    assert result is not None
```

**Mocking Example:**
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mock():
    """Test with mocked dependency."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = b"cached_value"

    with patch('src.module.get_redis_client', return_value=mock_redis):
        result = await function_using_redis()
        assert result == "cached_value"
```

### Coverage Configuration

**File:** `pytest.ini`

**Minimum coverage:** 60% (configurable)

**View coverage:**
```bash
# Terminal output
pytest --cov=src --cov-report=term-missing

# HTML report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest --cov=src --cov-report=xml
```

**Coverage exclusions:**
- Test files
- `if __name__ == "__main__"`
- `pragma: no cover`
- Type checking blocks

### Continuous Testing

**Watch mode (requires pytest-watch):**
```bash
pip install pytest-watch
ptw
```

---

## Frontend Testing (Cypress)

### Test Structure

```
apps/web/
├── cypress/
│   ├── e2e/
│   │   └── dashboard.cy.ts        # E2E tests
│   ├── support/
│   │   ├── e2e.ts                 # Global setup
│   │   └── commands.ts            # Custom commands
│   └── fixtures/                  # Test data
├── src/
│   └── **/*.cy.tsx                # Component tests
└── cypress.config.ts              # Cypress config
```

### Running E2E Tests

**Headless mode (CI):**
```bash
cd apps/web
npm run test:e2e
```

**Interactive mode (development):**
```bash
cd apps/web
npm run test:e2e:open
```

**Specific spec:**
```bash
npx cypress run --spec "cypress/e2e/dashboard.cy.ts"
```

**Chrome browser:**
```bash
npx cypress run --browser chrome
```

### Running Component Tests

**Headless:**
```bash
npm run test:component
```

**Interactive:**
```bash
npm run test:component:open
```

### Writing E2E Tests

**Example:**
```typescript
// cypress/e2e/dashboard.cy.ts

describe('Dashboard', () => {
  beforeEach(() => {
    cy.visit('/')
  })

  it('should load successfully', () => {
    cy.contains('Social Trend Agent').should('be.visible')
  })

  it('should submit a query', () => {
    // Intercept API call
    cy.intercept('POST', '/api/tasks', {
      statusCode: 200,
      body: { task_id: '123', status: 'submitted' }
    }).as('submitTask')

    // Fill form
    cy.get('input[type="text"]').type('AI trends 2025')
    cy.get('button[type="submit"]').click()

    // Verify
    cy.wait('@submitTask')
    cy.contains(/success/i).should('exist')
  })
})
```

### Custom Commands

**Define in** `cypress/support/commands.ts`:
```typescript
Cypress.Commands.add('login', (username, password) => {
  cy.request('POST', '/api/auth/login', { username, password })
})
```

**Use in tests:**
```typescript
cy.login('testuser', 'password123')
```

### Cypress Best Practices

1. **Use data-cy attributes:**
```tsx
<button data-cy="submit-btn">Submit</button>
```
```typescript
cy.get('[data-cy="submit-btn"]').click()
```

2. **Avoid hardcoded waits:**
```typescript
// ❌ Bad
cy.wait(5000)

// ✅ Good
cy.get('[data-cy="result"]', { timeout: 10000 }).should('exist')
```

3. **Use aliases:**
```typescript
cy.intercept('/api/insights').as('getInsights')
cy.wait('@getInsights')
```

4. **Clean state between tests:**
```typescript
beforeEach(() => {
  cy.clearLocalStorage()
  cy.clearCookies()
})
```

### Debugging Tests

**Pause test:**
```typescript
cy.pause()
```

**Debug commands:**
```typescript
cy.get('button').debug()
```

**Take screenshot:**
```typescript
cy.screenshot('my-screenshot')
```

---

## Coverage Reports

### Backend Coverage

**Generate report:**
```bash
pytest --cov=src --cov-report=html
```

**View report:**
```bash
open htmlcov/index.html
```

**Terminal report:**
```bash
pytest --cov=src --cov-report=term-missing
```

**Example output:**
```
---------- coverage: platform darwin, python 3.11.7 -----------
Name                                           Stmts   Miss  Cover   Missing
----------------------------------------------------------------------------
src/infrastructure/cache.py                      120     12    90%   45-48, 92
src/infrastructure/storage/async_redis_cache.py   95      8    92%   155-162
----------------------------------------------------------------------------
TOTAL                                           2145    430    80%
```

### Coverage Goals

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| `infrastructure/cache.py` | 90% | 95% | Medium |
| `infrastructure/storage/async_redis_cache.py` | 92% | 95% | Medium |
| `api/routes/dashboard.py` | 45% | 80% | **High** |
| `core/routing.py` | 0% | 75% | **High** |
| `core/gateway.py` | 0% | 75% | **High** |
| `agents/*/graph.py` | 20% | 70% | Medium |

### Frontend Coverage

**Cypress doesn't provide code coverage by default.**

To add coverage:
```bash
npm install --save-dev @cypress/code-coverage nyc
```

Configure in `vite.config.ts`:
```typescript
import istanbul from 'vite-plugin-istanbul'

plugins: [
  react(),
  istanbul({
    include: 'src/*',
    exclude: ['node_modules', 'test/'],
    extension: ['.js', '.ts', '.tsx']
  })
]
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml

name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run tests
        run: |
          pytest --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd apps/web
          npm ci

      - name: Run E2E tests
        run: |
          cd apps/web
          npm run test:e2e

      - name: Upload screenshots
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: cypress-screenshots
          path: apps/web/cypress/screenshots
```

---

## Troubleshooting

### Common Issues

**1. Redis connection failed:**
```
Solution: Start Redis with docker-compose up redis
```

**2. Async tests not running:**
```python
# Install pytest-asyncio
pip install pytest-asyncio

# Add to test file
import pytest
@pytest.mark.asyncio
async def test_async():
    pass
```

**3. Cypress not found:**
```bash
cd apps/web
npm install --save-dev cypress
```

**4. Coverage not updating:**
```bash
# Clear cache
pytest --cache-clear
rm -rf .pytest_cache htmlcov .coverage
```

---

## Additional Resources

- **Pytest Docs:** https://docs.pytest.org/
- **Cypress Docs:** https://docs.cypress.io/
- **Coverage.py:** https://coverage.readthedocs.io/
- **pytest-asyncio:** https://github.com/pytest-dev/pytest-asyncio

---

## Quick Reference

**Backend:**
```bash
pytest                          # All tests
pytest -m unit                  # Unit only
pytest -v                       # Verbose
pytest --cov=src               # With coverage
pytest -n auto                  # Parallel
```

**Frontend:**
```bash
npm run test:e2e               # E2E headless
npm run test:e2e:open          # E2E interactive
npm run test:component         # Component tests
```

**Coverage:**
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```
