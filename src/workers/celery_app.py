from celery import Celery
from src.config_loader import load_config
import sys

config = load_config()

celery_app = Celery(
    "askpolicy",
    broker  = config["celery"]["broker"],
    backend = config["celery"]["backend"]
)

celery_app.conf.update(
    task_serializer   = "json",
    result_serializer = "json",
    accept_content    = ["json"],
    timezone          = "UTC",

    # Fix for Windows
    worker_pool                  = "solo",
    worker_concurrency           = 1,
    worker_prefetch_multiplier   = 1,
)

# Required for Windows
if __name__ == "__main__":
    celery_app.start()