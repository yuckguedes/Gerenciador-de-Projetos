from fastapi import FastAPI
from app.api.routes import auth, projects, tasks

app = FastAPI(title="Desafio API")

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
