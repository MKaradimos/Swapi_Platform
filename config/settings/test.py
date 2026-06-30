from .base import *  # noqa: F401,F403

DEBUG = False

# Fast password hashing speeds up auth-heavy test suites significantly.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Celery tasks run synchronously and inline so tests don't need a real
# broker/worker, while still exercising the actual task code.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    "sync": "1000/min",
    "vote": "1000/min",
    "auth": "1000/min",
}
