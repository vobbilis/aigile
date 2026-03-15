import asyncio
import csv
import io
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from alert_store import AlertStore
from models import AlertRuleIn, AlertRuleOut, MetricIn, MetricOut, MetricSummary
from store import MetricStore

store = MetricStore()
alert_store = AlertStore()


async def _evaluate_loop() -> None:
    while True:
        await asyncio.sleep(10)
        alert_store.evaluate(store)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    task = asyncio.create_task(_evaluate_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Metrics Dashboard API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/metrics", response_model=MetricOut, status_code=201)
def submit_metric(metric: MetricIn) -> MetricOut:
    return store.add(metric)


@app.get("/metrics", response_model=list[MetricOut])
def list_metrics(tag: list[str] = Query(default=[])) -> list[MetricOut]:
    parsed_tags: list[tuple[str, str]] = []
    for t in tag:
        if ":" not in t:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag format '{t}'. Expected 'key:value'.",
            )
        key, value = t.split(":", 1)
        parsed_tags.append((key, value))
    return store.filter_by_tags(parsed_tags)


@app.get("/metrics/summary", response_model=MetricSummary)
def metrics_summary() -> MetricSummary:
    data = store.summary()
    return MetricSummary(**data)


@app.get("/metrics/export")
def export_metrics(format: str = "csv", tag: list[str] = Query(default=[])) -> StreamingResponse:
    if format != "csv":
        raise HTTPException(status_code=400, detail="Unsupported format. Use format=csv")

    # Parse tag filters (same logic as list_metrics)
    parsed_tags: list[tuple[str, str]] = []
    for t in tag:
        if ":" not in t:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tag format '{t}'. Expected 'key:value'.",
            )
        key, value = t.split(":", 1)
        parsed_tags.append((key, value))

    # Get metrics filtered by tags (returns all if no tags specified)
    metrics = store.filter_by_tags(parsed_tags)

    # Write to CSV buffer
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(["id", "name", "value", "tags", "timestamp"])

    # Write data rows
    for metric in metrics:
        writer.writerow(
            [metric.id, metric.name, metric.value, json.dumps(metric.tags), metric.timestamp]
        )

    # Return streaming response
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="metrics.csv"'},
    )


@app.get("/metrics/{name}/history", response_model=list[MetricOut])
def get_metric_history(name: str, limit: int = 20) -> list[MetricOut]:
    results = store.history(name, limit)
    if not results:
        raise HTTPException(status_code=404, detail=f"No history found for '{name}'")
    return results


@app.get("/metrics/{name}", response_model=list[MetricOut])
def get_metric(name: str) -> list[MetricOut]:
    results = store.by_name(name)
    if not results:
        raise HTTPException(status_code=404, detail=f"No metrics found for '{name}'")
    return results


@app.delete("/metrics/{name}")
def delete_metric(name: str) -> dict[str, int]:
    deleted = store.delete(name)
    alerts_deleted = alert_store.delete_rules_by_metric_name(name)
    return {"deleted": deleted, "alerts_deleted": alerts_deleted}


@app.post("/alerts", response_model=AlertRuleOut, status_code=201)
def create_alert(rule: AlertRuleIn) -> AlertRuleOut:
    return alert_store.add_rule(rule)


@app.get("/alerts", response_model=list[AlertRuleOut])
def list_alerts() -> list[AlertRuleOut]:
    return alert_store.all_rules()


@app.delete("/alerts/{rule_id}")
def delete_alert(rule_id: str) -> dict[str, int]:
    deleted = alert_store.delete_rule(rule_id)
    return {"deleted": deleted}
