from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, Optional
import time
import json, subprocess, sys
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="iMouseGuard Manual Trigger API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


HOOK_PATH = Path(__file__).resolve().parents[2] / "bin" / "imouse_hook_alert.py"

class TriggerPayload(BaseModel):
    # Keep it flexible first. We will tighten this later.
    behavior: str
    severity: str = "INFO"
    event_id: Optional[int] = None
    monitor_id: Optional[int] = None
    note: Optional[str] = None
    meta: Dict[str, Any] = {}

@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}

@app.post("/trigger")
@app.post("/trigger")
def trigger(payload: TriggerPayload):
    data = payload.model_dump()

    eid = str(payload.event_id or 0)
    mid = str(payload.monitor_id or 0)

    p = subprocess.Popen(
        [sys.executable, str(HOOK_PATH), eid, mid],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = p.communicate(input=json.dumps(data))

    return {
        "received": True,
        "exit_code": p.returncode,
        "stdout": out[-2000:],
        "stderr": err[-2000:],
    }

