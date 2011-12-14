import os
from config import SCRAPER_DATA_PATH
from urlparse import urlparse
import scraperwiki

def scrape (url, params = None):
    f = None
    parsed_url = urlparse(url)
    root_folder_name = SCRAPER_DATA_PATH + "/page_cache"
    folder_name = root_folder_name + "/" + parsed_url.netloc + os.path.dirname(parsed_url.path)
    file_name = os.path.basename(url)
    file_abspath = folder_name + "/" +file_name

    try:
        os.makedirs(folder_name)
    except OSError:
        None
        
    try:
        os.chdir(folder_name)
        f = open(file_abspath)
        print "Reading %s from local cache at %s" % (url, file_abspath)
        html = f.read()
    except IOError:
        print "Downloading %s" % url
        html = scraperwiki.scrape(url, params)
        f = open(file_abspath, 'w')
        f.write(html)
    finally:
        if f is not None:
            f.close()

    return html
