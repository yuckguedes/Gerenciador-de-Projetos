from fastapi import FastAPI

app = FastAPI(title="Desafio API")


@app.get("/health")
def health():
    return {"status": "ok"}
