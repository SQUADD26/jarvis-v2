"""Entry point for running the API server: python -m jarvis.api"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "jarvis.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
