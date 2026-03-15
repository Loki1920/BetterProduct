"""
Optional FastAPI REST backend.
Run: uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="BetterProduct API",
    description="Find and compare products across e-commerce platforms.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompareRequest(BaseModel):
    url: str


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/platforms")
async def platforms():
    return {
        "platforms": [
            {"name": "Amazon", "domain": "amazon.com"},
            {"name": "eBay",   "domain": "ebay.com"},
            {"name": "Walmart","domain": "walmart.com"},
        ]
    }


@app.post("/compare")
async def compare(req: CompareRequest):
    try:
        from backend.engine import comparison_engine
        result = await comparison_engine.compare(req.url)
        return {"success": True, "result": result.model_dump(mode="json")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
