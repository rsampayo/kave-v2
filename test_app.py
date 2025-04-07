from fastapi import FastAPI

app = FastAPI(title="Test App")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint for testing."""
    return {"message": "Hello World"}
