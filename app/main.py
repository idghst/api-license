from fastapi import FastAPI

app = FastAPI(title="License API")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "License API"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
