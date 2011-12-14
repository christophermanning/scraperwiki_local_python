import base64

try    : import json
except : import simplejson as json


logfd = None   # set to os.fdopen(3, 'w', 0) for consuming json objects

def dumpMessage(d):
    val = json.dumps(d)
    logfd.write( "JSONRECORD(%d):%s\n" % (len(val), val,) )
    logfd.flush()


from utils import log, scrape, pdftoxml, swimport
import geo
import datastore
import sqlite
import metadata
import stacktrace
import newsql
