from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from tasks.eod_tasks import run_eod_tasks

scheduler = BackgroundScheduler()

# Schedule to run every day at 11:00 PM IST
scheduler.add_job(run_eod_tasks, CronTrigger(hour=23, minute=0, timezone='Asia/Kolkata'), id='eod_tasks_job')
