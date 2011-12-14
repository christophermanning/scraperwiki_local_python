#!/usr/bin/env python
# utils.py
# David Jones, ScraperWiki Limited

from __future__ import with_statement

"""ScraperWiki Utils, see
https://scraperwiki.com/docs/python/python_help_documentation/
"""

__version__ = "ScraperWiki_0.0.1"

import cgi
import datetime
import imp
import os
import sys
import tempfile
import traceback
import urllib
import urllib2

try:
  import json
except:
  import simplejson as json

import scraperwiki   # in order to get dumpMessage function
    
    
# this will be useful for profiling the code, 
# it should return an output in json that you can click on to take you to the correct line
# see formatting in scrape 
def log(message=""):
    '''send message to console and the firebox logfile with a piece of the stack trace'''
    stack = traceback.extract_stack()
    tail = len(stack) >= 3 and ", %s() line %d" % (stack[-3][2], stack[-3][1]) or ""  # go 2 levels up if poss
    now = datetime.datetime.now()
    str_now = now.strftime("%Y-%m-%d %H:%M:%S")
    logmessage = "log( %s )\t\t %s() line %d%s : %s" % (str(message), stack[-2][2], stack[-2][1], tail, str_now)
    scraperwiki.dumpMessage({'message_type': 'console', 'content': logmessage})


def httpresponseheader(headerkey, headervalue):
    '''Set (certain) HTTP Response Header.  For example
    scraperwiki.utils.httpresponseheader('Content-Type', 'text/plain')
    '''

    # Messages of this type are picked up and specially interpreted by
    # viewsrpc.rpcexecute
    scraperwiki.dumpMessage({'message_type': 'httpresponseheader', 'headerkey': headerkey, 'headervalue': headervalue})

def httpstatuscode(statuscode):
    """Experimental and Internal.  Sets the HTTP Status Code to be
    *statuscode* which should be an int.
    """

    # Messages of this type are picked up and specially interpreted by
    # viewsrpc.rpcexecute
    scraperwiki.dumpMessage(
      {'message_type': 'httpstatuscode', 'statuscode': statuscode})


# to be deprecated if possible
def GET():
    return dict(cgi.parse_qsl(os.getenv("QUERY_STRING", "")))


urllib2opener = None
def urllibSetup(http_proxy):
        # this proxies for urllib
    os.environ['http_proxy' ] = http_proxy  
        # this proxies for urllib2
    global urllib2opener
    urllib2handlers = [ urllib2.ProxyHandler({'http':http_proxy }) ]
    urllib2opener = urllib2.build_opener(*urllib2handlers)
    urllib2.install_opener(urllib2opener)


#  Scrape a URL optionally with parameters. This is effectively a wrapper around
#  urllib2.orlopen().
#
def scrape (url, params = None) :
    data = params and urllib.urlencode(params) or None
   
    fin  = urllib2.urlopen(url, data)
    text = fin.read()
    fin.close()   # get the mimetype here

    return text


def pdftoxml(pdfdata):
    """converts pdf file to xml file"""
    pdffout = tempfile.NamedTemporaryFile(suffix='.pdf')
    pdffout.write(pdfdata)
    pdffout.flush()

    xmlin = tempfile.NamedTemporaryFile(mode='r', suffix='.xml')
    tmpxml = xmlin.name # "temph.xml"
    cmd = '/usr/bin/pdftohtml -xml -nodrm -zoom 1.5 -enc UTF-8 -noframes "%s" "%s"' % (pdffout.name, os.path.splitext(tmpxml)[0])
    cmd = cmd + " >/dev/null 2>&1" # can't turn off output, so throw away even stderr yeuch
    os.system(cmd)

    pdffout.close()
    #xmlfin = open(tmpxml)
    xmldata = xmlin.read()
    xmlin.close()
    return xmldata


# code adapted from http://docs.python.org/library/imp.html#examples-imp
# ideally there is a way to seamlessly overload the __import__ function and get us to call out like this
# it should also be able to explicitly refer to a named revision
def swimport(name, swinstance="https://scraperwiki.com"):
    import imp
    try:
        return sys.modules[name]
    except KeyError:
        pass

    #fp, pathname, description = imp.find_module(name)
    url = "%s/editor/raw/%s" % (swinstance, name)
    modulecode = urllib.urlopen(url).read() + "\n"
    
    modulefile = tempfile.NamedTemporaryFile(suffix='.py')
    modulefile.write(modulecode)
    modulefile.flush()
    fp = open(modulefile.name)
    return imp.load_module(name, fp, modulefile.name, (".py", "U", 1))

class SWImporter(object):
    def __init__(self, swinstance="https://scraperwiki.com"):
        self.swinstance = swinstance

    def find_module(self, name, path=None):
        return self

    def load_module(self, name):
        try:
            return self.use_standard_import(name)
        except:
            return self.import_from_scraperwiki(name)

    def use_standard_import(self, name):
        return imp.load_module(imp.find_module(name))

    def import_from_scraperwiki(self, name):
        try:
            url = "%s/editor/raw/%s" % (self.swinstance, name)
            modulecode = urllib2.urlopen(url).read() + "\n"

            # imp.load_module really needs a file, cannot use StringIO
            modulefile = tempfile.NamedTemporaryFile(suffix='.py')
            modulefile.write(modulecode)
            modulefile.flush()

            with open(modulefile.name) as fp:
                return imp.load_module(name, fp, modulefile.name, (".py", "U", imp.PY_SOURCE))
        except:
            raise ImportError

# callback to a view with parameter lists (cross language capability)
def jsviewcall(name, **args):
    url = "https://scraperwiki.com/views/%s/run/?%s" % (name, urllib.urlencode(args))
    response = urllib.urlopen(url).read()
    try:
        return json.loads(response)
    except ValueError:
        return response
    
