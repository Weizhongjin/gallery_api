from fastapi import FastAPI
from app.auth.router import router as auth_router
from app.assets.router import router as assets_router
from app.users.router import router as users_router
from app.taxonomy.router import router as taxonomy_router
from app.lookbooks.router import router as lookbooks_router
from app.search.router import router as search_router
from app.jobs.router import router as jobs_router
from app.products.router import router as products_router
from app.aigc.router import router as aigc_router

app = FastAPI(title="Cloth Gallery API", version="1.1.0")
app.include_router(auth_router)
app.include_router(assets_router)
app.include_router(users_router)
app.include_router(taxonomy_router)
app.include_router(lookbooks_router)
app.include_router(search_router)
app.include_router(jobs_router)
app.include_router(products_router)
app.include_router(aigc_router)


@app.get("/health")
def health():
    return {"status": "ok"}
