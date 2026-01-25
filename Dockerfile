FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .
COPY uv.lock* .

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY src/ src/

# Create non-root user
RUN useradd -m jarvis && chown -R jarvis:jarvis /app
USER jarvis

# Run
CMD ["uv", "run", "python", "-m", "jarvis.main"]
