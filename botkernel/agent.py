import os
import time
import uuid
import httpx
from botkernel.security import agent_headers

name = os.getenv("AGENT_NAME","cost")
with httpx.Client(base_url="http://api:8000",timeout=10,headers=agent_headers()) as client:
    for tick in range(60):
        client.post("/agents/"+name).raise_for_status()
        r = client.get("/telemetry").json()[0]
        if name == "cost":
            target = max(1,r["capacity"]-1) if r['capacity']>3 else r['capacity']
        else:
            target = min(12,r["capacity"]+1) if r['latency_p95']>80 else r['capacity']
        if target == r['capacity']:
            time.sleep(1)
            continue
        response = client.post("/actions",json={"agent":name,"workflow":"demo","idempotency_key":str(uuid.uuid4()),"resource":r["id"],"expected_version":r["version"],"capacity":target})
        print(name,tick,response.status_code,response.text,flush=True)
        time.sleep(1)
