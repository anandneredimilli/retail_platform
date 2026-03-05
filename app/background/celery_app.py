from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "retail_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.background.tasks"],
)
celery_app.conf.update(task_serializer="json", result_serializer="json",
                       accept_content=["json"], timezone="UTC", enable_utc=True)
celery_app.conf.beat_schedule = {
    "aggregate-daily-sales": {
        "task": "app.background.tasks.aggregate_daily_sales",
        "schedule": crontab(hour=0, minute=0),
    },
    "daily-inventory-snapshot": {
        "task": "app.background.tasks.take_daily_inventory_snapshot",
        "schedule": crontab(hour=23, minute=55),
    },
    "compute-kpi-cache": {
        "task": "app.background.tasks.compute_kpi_cache",
        "schedule": crontab(minute=0),
    },
}