from fastapi import FastAPI
from app.auth.router import router as auth_router
from app.assets.router import router as assets_router

app = FastAPI(title="Cloth Gallery API", version="1.0.0")
app.include_router(auth_router)
app.include_router(assets_router)


@app.get("/health")
def health():
    return {"status": "ok"}
