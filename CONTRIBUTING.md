# Contributing to Frigate AI Proxy

We welcome contributions, bug reports, and enhancements from the community!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/israelsaba/frigate-ai-proxy.git
   cd frigate-ai-proxy
   ```

2. Install dependencies with `uv`:
   ```bash
   uv sync
   ```

3. Run the development server:
   ```bash
   make run
   ```

## Pull Request Guidelines

Before submitting a PR:
1. Run the linter and formatters:
   ```bash
   make lint
   ```
2. Run the test suite:
   ```bash
   make test
   ```
3. Ensure no secrets, API keys, or private endpoints are committed.
4. Keep changes focused, documented, and covered by automated tests.
