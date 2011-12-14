#!/usr/bin/env python

import scraperwiki.sqlite

metadatamessagedone = False

# These are DEPRECATED and just here for compatibility
def get(metadata_name, default=None):
    global metadatamessagedone
    if not metadatamessagedone:
        print "*** instead of metadata.get('%s') please use\n    scraperwiki.sqlite.get_var('%s')" % (metadata_name, metadata_name)
        metadatamessagedone = True
    return scraperwiki.sqlite.get_var(metadata_name, default)

# These are DEPRECATED and just here for compatibility
def save(metadata_name, value):
    global metadatamessagedone
    if not metadatamessagedone:
        print "*** instead of metadata.save('%s') please use\n    scraperwiki.sqlite.save_var('%s')" % (metadata_name, metadata_name)
        metadatamessagedone = True
    return scraperwiki.sqlite.save_var(metadata_name, value)
