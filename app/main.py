from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import init_db
from app.seed import seed_demo_data
from app.routes.api import router
from governance.api import router as governance_router

app=FastAPI(title=settings.app_name,version="1.0.0",
 description="Governed ExpenseClaim Agent backend: Person 1 core with Person 3 integration ports.")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(router)
app.include_router(governance_router, prefix="/api")


@app.on_event("startup")
def startup():
    init_db()
    seed_demo_data()

@app.get("/health")
def health(): return {"status":"ok","service":settings.app_name}
