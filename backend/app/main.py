from fastapi import FastAPI

app = FastAPI(title="FinFlow", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "FinFlow API"}