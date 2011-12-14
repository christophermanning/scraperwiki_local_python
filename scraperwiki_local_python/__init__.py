import os, sys
try    : import json
except : import simplejson as json

sys.path.insert(0, os.path.dirname(__file__) + "/scraperwiki/scraperlibs/python")
sys.path.insert(0, os.path.dirname(__file__) + "/scraperwiki/services/datastore")

import datastore
from scraperwiki import sqlite
from utils import scrape
from scraperwiki import utils
from scraperwiki import geo

sys.modules['scraperwiki'].datastore = datastore
sys.modules['scraperwiki'].dumpMessage = lambda msg: sys.stdout.write(json.dumps(msg))
