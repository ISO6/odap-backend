from functools import wraps

from cachetools import TTLCache

cache = TTLCache(
    maxsize=100,
    ttl=3600,
)

# TODO:将来使用Redis
def cacheable(key: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if key in cache:
                print("in cache")
                return cache[key]
            result = await func(
                *args,
                **kwargs,
            )
            cache[key] = result
            return result
        return wrapper
    return decorator
