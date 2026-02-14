FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for native packages (webrtcvad, pyaudio, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential portaudio19-dev && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .
COPY uv.lock* .

# Install dependencies
RUN uv sync --no-dev

# Copy source code
COPY src/ src/

# Create non-root user
RUN useradd -m jarvis && chown -R jarvis:jarvis /app
USER jarvis

# Run
CMD ["uv", "run", "python", "-m", "jarvis.main"]
