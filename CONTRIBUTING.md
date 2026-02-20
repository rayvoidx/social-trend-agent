# Contributing to Social Trend Agent

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- Redis (optional, graceful fallback)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/rayvoidx/social-trend-agent.git
cd social-trend-agent

# Python setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Environment configuration
cp .env.example .env
# Edit .env and add your API keys

# Run tests
pytest tests/ -v

# Start the API server
python main.py
```

### Frontend Setup

```bash
cd apps/web
npm install
npm run dev
```

## Project Structure

```
src/
├── agents/          # LangGraph agent definitions
│   ├── news_trend/  # News trend analysis agent
│   ├── social_trend/# Social media trend agent
│   └── viral_video/ # Viral video analysis agent
├── api/             # FastAPI routes and middleware
├── core/            # Shared core modules (state, routing, errors)
├── infrastructure/  # Redis cache, distributed workers
└── integrations/    # External service clients (LLM, MCP)
```

## Development Workflow

1. **Create a branch** from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the coding standards below.

3. **Run tests** and ensure they pass:

   ```bash
   pytest tests/ -v
   ```

4. **Run linting**:

   ```bash
   ruff check src/ tests/
   ruff format src/ tests/
   ```

5. **Submit a Pull Request** against `main`.

## Coding Standards

### Python

- **Style**: Follow [PEP 8](https://peps.python.org/pep-0008/), enforced via [Ruff](https://docs.astral.sh/ruff/)
- **Type hints**: Use type annotations for function signatures
- **Async**: Use `async/await` for I/O-bound operations in FastAPI routes
- **Models**: Use Pydantic v2 for request/response models
- **Line length**: 100 characters max

### TypeScript / React

- **Framework**: React 19 with TypeScript
- **Bundler**: Vite
- **Linting**: ESLint with TypeScript rules

### Testing

- **Framework**: pytest with pytest-asyncio
- **Coverage target**: 30% minimum (increasing toward 80%)
- **Test categories**:
  - `tests/unit/` — Fast, isolated unit tests
  - `tests/integration/` — Tests requiring service dependencies
- **Naming**: `test_*.py` files, `test_*` functions

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add viral video spike detection
fix: resolve Redis connection timeout
refactor: simplify orchestrator routing logic
docs: update API endpoint documentation
test: add orchestrator unit tests
```

## Reporting Issues

When reporting bugs, please include:

- Python version and OS
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages

## License

By contributing, you agree that your contributions will be licensed under the [BSD-3-Clause License](./LICENSE).
