from slowapi import Limiter
from slowapi.util import get_remote_address

# Basic, single-instance, in-memory rate limiting — no Redis, matching this
# project's "no overengineering" stance. Would need a shared backend
# (Redis) to work correctly across multiple processes/instances; fine for
# now since this runs as one process. default_limits applies to every
# route automatically (via SlowAPIMiddleware in main.py); routes that need
# a stricter limit (auth, chat) declare their own with @limiter.limit(...),
# which overrides the default for that route.
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
