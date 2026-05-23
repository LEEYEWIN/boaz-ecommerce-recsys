import redis, os, json

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

def get(key: str):
    return r.get(key)

def set_with_ttl(key: str, value, ttl: int = 3600):
    r.setex(key, ttl, json.dumps(value))