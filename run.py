"""
Run the Glupper API server
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",  # Use localhost instead of binding to all interfaces
        port=8000,
        reload=True,
        workers=4,
    )
