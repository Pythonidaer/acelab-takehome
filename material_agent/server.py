"""Local HTTP API for the Material Recommendation web UI (SSE)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .agent import run_agent

app = FastAPI(title="Material Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendBody(BaseModel):
    prompt: str = Field(..., min_length=1)
    trace: bool = False


_STREAM_END = object()


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/recommend/stream")
async def recommend_stream(body: RecommendBody) -> StreamingResponse:
    queue: asyncio.Queue[Any] = asyncio.Queue()

    async def on_event(ev: dict[str, Any]) -> None:
        await queue.put(ev)

    async def runner() -> None:
        trace_capture: list[str] = []
        try:
            report = await run_agent(
                body.prompt.strip(),
                on_event=on_event,
                stream_trace=body.trace,
                trace_capture=trace_capture,
            )
            await queue.put(
                {
                    "kind": "complete",
                    "report": report.model_dump(mode="json"),
                    "trace": trace_capture,
                }
            )
        except Exception as e:
            await queue.put({"kind": "error", "message": str(e)})
        finally:
            await queue.put(_STREAM_END)

    asyncio.create_task(runner())

    async def events() -> Any:
        while True:
            item = await queue.get()
            if item is _STREAM_END:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


def main() -> None:
    import uvicorn

    uvicorn.run("material_agent.server:app", host="127.0.0.1", port=8000)
