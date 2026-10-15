
import json, urllib.request, time
URL="http://127.0.0.1:8080/mcp"
def _rpc(body, sid=None, timeout=240):
    h={"Content-Type":"application/json","Accept":"application/json, text/event-stream"}
    if sid: h["mcp-session-id"]=sid
    req=urllib.request.Request(URL,data=json.dumps(body).encode(),headers=h,method="POST")
    r=urllib.request.urlopen(req,timeout=timeout)
    return r.headers.get("mcp-session-id"), r.read().decode()
def _last(t):
    out=None
    for ln in t.split("\n"):
        if ln.startswith("data:"):
            try:
                j=json.loads(ln[5:])
                if "result" in j or "error" in j: out=j
            except: pass
    return out
_sid=None
def unity(name, **args):
    global _sid
    if not _sid:
        _sid,_=_rpc({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"c","version":"0"}}})
        _rpc({"jsonrpc":"2.0","method":"notifications/initialized"},_sid)
    _,t=_rpc({"jsonrpc":"2.0","id":int(time.time()*1000)%10**9,"method":"tools/call","params":{"name":name,"arguments":args}},_sid)
    j=_last(t)
    try: return json.loads(j["result"]["content"][0]["text"])
    except Exception: return j
