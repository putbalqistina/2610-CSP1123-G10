import schedule
import time
from app import check_deadlines

schedule.every(10).seconds.do(check_deadlines)

while True:
    schedule.run_pending()
    time.sleep(60)