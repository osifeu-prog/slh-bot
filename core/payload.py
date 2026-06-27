import json

def normalize(p):
    if p is None:
        return {}
    if isinstance(p, dict):
        return p
    if isinstance(p, str):
        try:
            return json.loads(p)
        except:
            return {"value": p}
    return {"value": str(p)}
