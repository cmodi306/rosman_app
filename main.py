from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

from ros_manager import *

import asyncio
import os
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for node_key in list(RUNNING_NODES.keys()):
        pkg, node = node_key.split("/", 1)
        stop_node(pkg, node)

app = FastAPI(lifespan=lifespan)

@app.get("/browse")
async def browse_file():
    try:
        result = subprocess.run(
            ["zenity", "--file-selection", "--title=Select ROS Setup File"],
            capture_output=True, text=True
        )
        return {"path": result.stdout.strip()}
    except FileNotFoundError:
        return {"path": "", "error": "unavailable"}

@app.post("/source")
async def source_and_get_packages(setup_path:str):
    try:
        return {"error": not source_ws(setup_path),
                "packages": get_packages_list(setup_path)
                }
    except:
        return False

@app.post("/start")
async def start(package_name: str, node_name: str):
    start_node(package_name, node_name)

@app.post("/stop")
async def stop(package_name:str, node_name:str):
    stop_node(package_name, node_name)

@app.get("/logs/stream")
async def stream_logs(package_name: str, node_name: str):
    node_key = f"{package_name}/{node_name}"
    q = asyncio.Queue()
    NODE_LOG_QUEUES.setdefault(node_key, []).append(q)

    async def event_gen():
        try:
            for line in list(NODE_LOGS.get(node_key, [])):
                yield f"data: {line}\n\n"
            while True:
                try:
                    line = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {line}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            NODE_LOG_QUEUES.get(node_key, []).remove(q)

    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/status")
async def status():
    return {"running": list(RUNNING_NODES.keys())}

@app.get("/")
async def root():
    return FileResponse(os.path.join(PROJECT_ROOT, "templates", "index.html"))