try   : import json
except: import simplejson as json

import os
import datalib
import time
from config import SCRAPER_DATA_PATH

sqlite_db = None

def request(request):
    global sqlite_db
    if sqlite_db is None:
        sqlite_db = datalib.SQLiteDatabase(None, os.getcwd(), SCRAPER_DATA_PATH, None, str(time.time()), None)
    return sqlite_db.process(request)
