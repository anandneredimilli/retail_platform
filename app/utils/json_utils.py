from decimal import Decimal

def normalize_json(data):
    if isinstance(data, dict):
        return {k: normalize_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [normalize_json(v) for v in data]
    if isinstance(data, Decimal):
        return float(data)   # or str(data)
    return data