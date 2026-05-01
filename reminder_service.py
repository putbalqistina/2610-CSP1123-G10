import schedule
import time
from app import check_deadlines

schedule.every().day.at("08:00").do(check_deadlines)

while True:
    schedule.run_pending()
    time.sleep(60)