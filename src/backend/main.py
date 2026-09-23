from fastapi import FastAPI
import os

app = FastAPI(title="Talk-to-my-data Backend (Minimal Stub)")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Talk-to-my-data backend container is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
