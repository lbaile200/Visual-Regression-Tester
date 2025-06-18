from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = BackgroundScheduler()

def schedule_job(job_id, func, interval_minutes):
    scheduler.add_job(func, trigger=IntervalTrigger(minutes=interval_minutes), id=job_id, replace_existing=True)

def remove_job(job_id):
    scheduler.remove_job(job_id)
