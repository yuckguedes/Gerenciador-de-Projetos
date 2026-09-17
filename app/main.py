from fastapi import FastAPI
from app.api.routes import auth, projects

app = FastAPI(title="Desafio API")

app.include_router(auth.router)
app.include_router(projects.router)


@app.get("/health")
def health():
    return {"status": "ok"}
