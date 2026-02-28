from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import MetricIn, MetricOut
from store import MetricStore

app = FastAPI(title="Metrics Dashboard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = MetricStore()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/metrics", response_model=MetricOut, status_code=201)
def submit_metric(metric: MetricIn) -> MetricOut:
    return store.add(metric)


@app.get("/metrics", response_model=list[MetricOut])
def list_metrics() -> list[MetricOut]:
    return store.all()


@app.get("/metrics/{name}", response_model=list[MetricOut])
def get_metric(name: str) -> list[MetricOut]:
    results = store.by_name(name)
    if not results:
        raise HTTPException(status_code=404, detail=f"No metrics found for '{name}'")
    return results


@app.delete("/metrics/{name}")
def delete_metric(name: str) -> dict[str, int]:
    deleted = store.delete(name)
    return {"deleted": deleted}
