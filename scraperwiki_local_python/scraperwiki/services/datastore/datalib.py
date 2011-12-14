from twisted.python import log

import ConfigParser
import hashlib
import types
import os
import string
import time
import datetime
import sqlite3
import signal
import base64
import shutil
import re
import sys
import logging
import urllib

try:
    import json
except:
    import simplejson as json


class TimeoutException(Exception): 
    pass 

def authorizer_readonly(action_code, tname, cname, sql_location, trigger):
    log.msg("authorizer_readonly: %s, %s, %s, %s, %s" % (action_code, tname, cname, sql_location, trigger))

    readonlyops = [ sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_DETACH, 31 ]  # 31=SQLITE_FUNCTION missing from library.  codes: http://www.sqlite.org/c3ref/c_alter_table.html
    if action_code in readonlyops:
        return sqlite3.SQLITE_OK

    if action_code == sqlite3.SQLITE_PRAGMA:
        if tname in ["table_info", "index_list", "index_info", "page_size"]:
            return sqlite3.SQLITE_OK

    # SQLite FTS (full text search) requires this permission even when reading, and
    # this doesn't let ordinary queries alter sqlite_master because of PRAGMA writable_schema
    if action_code == sqlite3.SQLITE_UPDATE and tname == "sqlite_master":
        return sqlite3.SQLITE_OK

    return sqlite3.SQLITE_DENY

def authorizer_attaching(action_code, tname, cname, sql_location, trigger):
    #print "authorizer_attaching", (action_code, tname, cname, sql_location, trigger)
    if action_code == sqlite3.SQLITE_ATTACH:
        return sqlite3.SQLITE_OK
    return authorizer_readonly(action_code, tname, cname, sql_location, trigger)

def authorizer_writemain(action_code, tname, cname, sql_location, trigger):
    #print "authorizer_writemain", (action_code, tname, cname, sql_location, trigger)
    if sql_location == None or sql_location == 'main':  
        return sqlite3.SQLITE_OK
    return authorizer_readonly(action_code, tname, cname, sql_location, trigger)
    

class Database(object):
    def process(self):
        raise NotImplementedError

class SQLiteDatabase(Database):

    def __init__(self, ldataproxy, resourcedir, short_name, dataauth, runID, attachables):
        self.dataproxy = ldataproxy  # this is just to give access to self.dataproxy.connection.send()
        self.m_resourcedir = resourcedir
        self.short_name = short_name
        self.dataauth = dataauth
        self.runID = runID
        self.attachables = attachables
                
        self.m_sqlitedbconn = None
        self.m_sqlitedbcursor = None
        self.authorizer_func = None  
        self.sqlitesaveinfo = { }  # tablename -> info

        if self.short_name:
            self.scraperresourcedir = os.path.join(self.m_resourcedir, self.short_name)


    def close(self):
        try:
            if self.m_sqlitedbcursor:
                self.m_sqlitedbcursor.close()
            if self.m_sqlitedbconn:
                self.m_sqlitedbconn.close()
        except:
            pass
            
    def process(self, request):
        
        # Before we do any of these we should check the attachables that we have by running 
        # self.sqliteattach(request.get("name"), request.get("asname"))
        if self.attachables:
            for entry in json.loads(self.attachables):
                self.sqliteattach( entry['name'], entry['asname'] )
        
        if type(request) != dict:
            res = {"error":'request must be dict', "content":str(request)}
        elif "maincommand" not in request:
            res = {"error":'request must contain maincommand', "content":str(request)}
        elif request["maincommand"] == 'save_sqlite':
            res = self.save_sqlite(unique_keys=request["unique_keys"], data=request["data"], swdatatblname=request["swdatatblname"])
        elif request["maincommand"] == 'clear_datastore':
            res = self.clear_datastore()
        elif request["maincommand"] == 'undelete_datastore':
            res = self.undelete_datastore()
        elif request["maincommand"] == 'sqlitecommand':
            if request["command"] == "downloadsqlitefile":
                res = self.downloadsqlitefile(seek=request["seek"], length=request["length"])
            elif request["command"] == "datasummary":
                res = self.datasummary(request.get("limit", 10))
            elif request["command"] == "attach":
                res = self.sqliteattach(request.get("name"), request.get("asname"))
            elif request["command"] == "commit":
                res = self.sqlitecommit()

                # in the case of stream chunking there is one sendall in a loop in this function
        elif request["maincommand"] == "sqliteexecute":
            res = self.sqliteexecute(sqlquery=request["sqlquery"], data=request["data"], attachlist=request.get("attachlist"), streamchunking=request.get("streamchunking"))

        else:
            res = {"error":'Unknown maincommand: %s' % request["maincommand"]}
            log.msg(json.dumps(res), logLevel=logging.DEBUG)

        return res


    def undelete_datastore(self):
        restore_from = os.path.join(self.scraperresourcedir, "DELETED-defaultdb.sqlite")
        if os.path.isfile(restore_from):
            restore_to = os.path.join(self.scraperresourcedir, "defaultdb.sqlite")
            shutil.move(restore_from, restore_to)
        return {"status":"good"}
        

    def clear_datastore(self):
        scrapersqlitefile = os.path.join(self.scraperresourcedir, "defaultdb.sqlite")
        if os.path.isfile(scrapersqlitefile):
            deletedscrapersqlitefile = os.path.join(self.scraperresourcedir, "DELETED-defaultdb.sqlite")
            shutil.move(scrapersqlitefile, deletedscrapersqlitefile)
        return {"status":"good"}

    
            # To do this properly would need to ensure file doesn't change during this process
    def downloadsqlitefile(self, seek, length):
        scrapersqlitefile = os.path.join(self.scraperresourcedir, "defaultdb.sqlite")
        lscrapersqlitefile = os.path.join(self.short_name, "defaultdb.sqlite")
        if not os.path.isfile(scrapersqlitefile):
            return {"status":"No sqlite database"}
        
        result = { "filename":lscrapersqlitefile, "filesize": os.path.getsize(scrapersqlitefile)}
        if length == 0:
            return result
        
        fin = open(scrapersqlitefile, "rb")
        fin.seek(seek)
        content = fin.read(length)
        result["length"] = len(content)
        result["content"] = base64.encodestring(content)
        result['encoding'] = "base64"
        fin.close()
        
        return result
    
    
    def establishconnection(self, bcreate):
        
        # apparently not able to reset authorizer function after it has been set once, so have to redirect this way
        def authorizer_all(action_code, tname, cname, sql_location, trigger):
            #print "authorizer_all", (action_code, tname, cname, sql_location, trigger)
            return self.authorizer_func(action_code, tname, cname, sql_location, trigger)
        
        if self.dataauth == "fromfrontend":
            self.authorizer_func = authorizer_readonly
        elif self.dataauth == "draft" and self.short_name:
            self.authorizer_func = authorizer_readonly
        else:
            self.authorizer_func = authorizer_writemain
        
        
        def progress_handler():
            log.msg("progress on %s" % self.runID, logLevel=logging.DEBUG)
            
        
        if not self.m_sqlitedbconn:
            if self.short_name:
                if not os.path.isdir(self.scraperresourcedir):
                    if not bcreate: 
                        return False
                    os.mkdir(self.scraperresourcedir)
                scrapersqlitefile = os.path.join(self.scraperresourcedir, "defaultdb.sqlite")
                print 'Connecting to %s' % scrapersqlitefile 
                self.m_sqlitedbconn = sqlite3.connect(scrapersqlitefile, check_same_thread=False)
                log.msg('Connected to %s' % scrapersqlitefile, logLevel=logging.DEBUG )                
            else:
                self.m_sqlitedbconn = sqlite3.connect(":memory:", check_same_thread=False)   # draft scrapers make a local version
            self.m_sqlitedbconn.set_authorizer(authorizer_all)
#            try:
#                self.m_sqlitedbconn.set_progress_handler(progress_handler, 1000000)  # can be order of 0.4secs 
#            except AttributeError:
#                pass  # must be python version 2.6
            self.m_sqlitedbcursor = self.m_sqlitedbconn.cursor()
             
        return True
                
                
    def datasummary(self, limit):
        if not self.establishconnection(False):
            log.msg( 'Failed to connect to sqlite database for summary %s' % (self.short_name or 'draft'), logLevel=logging.WARNING )
            return {"status":"No sqlite database"} # don't change this return string, is a structured one

        log.msg('Performing datasummary for %s' % self.short_name, logLevel=logging.DEBUG )                
                        
        self.authorizer_func = authorizer_readonly
        total_rows = 0
        tables = { }
        try:
            for name, sql in list(self.m_sqlitedbcursor.execute("select name, sql from sqlite_master where type='table' or type='view'")):
                tables[name] = {"sql":sql}
                if limit != -1:
                    self.m_sqlitedbcursor.execute("select * from `%s` order by rowid desc limit ?" % name, (limit,))
                    if limit != 0:
                        rows = []
                        for r in self.m_sqlitedbcursor:
                            row = []                           
                            for c in r:
                                if type(c) == buffer:
                                    row.append( str(c).decode('ascii', 'replace') ) # in FTS3 _segments table this is just binary stuff, need to ignore bad chars
                                else:
                                    row.append(c)
                            rows.append(row)
                        tables[name]["rows"] = rows
                    tables[name]["keys"] = map(lambda x:x[0], self.m_sqlitedbcursor.description)
                tables[name]["count"] = list(self.m_sqlitedbcursor.execute("select count(1) from `%s`" % name))[0][0]
                total_rows += int(tables[name]["count"])
        except sqlite3.Error, e:
            return {"error":"datasummary: sqlite3.Error: "+str(e)}
        
        result = {"tables":tables, 'total_rows': total_rows }
        if self.short_name:
            scrapersqlitefile = os.path.join(self.scraperresourcedir, "defaultdb.sqlite")
            if os.path.isfile(scrapersqlitefile):
                result["filesize"] = os.path.getsize(scrapersqlitefile)
                 
        return result
    
    
    def sqliteexecute(self, sqlquery, data, attachlist, streamchunking):
        print "XXXX %s %s - %s %s" % (self.runID[:5], self.short_name, sqlquery, str(data)[:50])

        def timeout_handler(signum, frame):
            raise TimeoutException()

        timeout_len = 30

        self.establishconnection(True)
        try:
            # In the absence of a user toolkit for managing the database we will manually tweak
            # the timeout for creating indices
            if 'create index' in sqlquery.lower():
                timeout_len = 180
            
            # If the query hasn't run in timeout_len seconds then we'll timeout
            #signal.signal(signal.SIGALRM, timeout_handler)                
            #signal.alarm(timeout_len)  # should use set_progress_handler !!!!
            if data:
                self.m_sqlitedbcursor.execute(sqlquery, data)  # handle "(?,?,?)", (val, val, val)
            else:
                self.m_sqlitedbcursor.execute(sqlquery)
            #signal.alarm(0)

            #INSERT/UPDATE/DELETE/REPLACE), and commits transactions implicitly before a non-DML, non-query statement (i. e. anything other than SELECT
            #check that only SELECT has a legitimate return state

            keys = self.m_sqlitedbcursor.description and map(lambda x:x[0], self.m_sqlitedbcursor.description) or []

            # non-chunking return point
            if not streamchunking:
                rows = []
                for r in self.m_sqlitedbcursor:
                    row = []
                    for c in r:
                        if type(c) == buffer:
                            row.append( unicode(c) )
                        else:
                            row.append(c)
                    rows.append(row)
                return {"keys":keys, "data": rows}                
#                return {"keys":keys, "data":self.m_sqlitedbcursor.fetchall()}

                # this loop has the one internal jsend in it
            while True:
                odata = self.m_sqlitedbcursor.fetchmany(streamchunking)
                rows = []
                for r in odata:
                    row = []
                    for c in r:
                        if type(c) == buffer:
                            row.append(unicode(c))
                        else:
                            row.append(c)
                    rows.append(row)
                arg = {"keys":keys, "data":rows} 
                if len(odata) < streamchunking:
                    break
                arg["moredata"] = True
                log.msg("midchunk %s %d" % (self.short_name, len(odata),), logLevel=logging.DEBUG)
                self.dataproxy.connection.sendall(json.dumps(arg)+'\n')
            return arg
        except sqlite3.Error, e:
            print "user sqlerror %s %s" % (sqlquery[:1000], str(data)[:1000])
            log.err( e )
            return {"error":"sqliteexecute: sqlite3.Error: %s" % str(e)}
        except ValueError, ve:
            print "user sqlerror %s %s" % (sqlquery[:1000], str(data)[:1000])
            log.err( ve )            
            return {"error":"sqliteexecute: ValueError: %s" % str(ve)}
        except TimeoutException,tout:
            print "user sqltimeout %s %s" % (sqlquery[:1000], str(data)[:1000])
            log.err( ve )
            return { "error" : "Query timeout: %s" % str(tout) }


    def sqliteattach(self, name, asname):
        log.msg("attach to %s  %s as %s" % (self.short_name, name, asname), logLevel=logging.DEBUG)
        self.establishconnection(True)
        if self.authorizer_func == authorizer_writemain:
            self.m_sqlitedbconn.commit()  # otherwise a commit will be invoked by the attaching function
        
        log.msg("attachables: "+str(self.attachables), logLevel=logging.DEBUG)
        log.msg("requesting permission to attach %s to %s" % (self.short_name, name), logLevel=logging.INFO)
        aquery = {"command":"can_attach", "scrapername":self.short_name, "attachtoname":name, "username":"unknown"}
        ares = urllib.urlopen("%s?%s" % (self.dataproxy.attachauthurl, urllib.urlencode(aquery))).read()
        log.msg("permission to attach %s to %s response: %s" % (self.short_name, name, ares), logLevel=logging.INFO)
        if ares == "Yes":
            log.msg('Connection allowed', logLevel=logging.DEBUG)
        elif ares == "DoesNotExist":
            return {"error":"Does Not Exist %s" % name}
        else:
            return {"error":"no permission to attach to %s" % name}

        attachscrapersqlitefile = os.path.join(self.m_resourcedir, name, "defaultdb.sqlite")
        self.authorizer_func = authorizer_attaching
        try:
            self.m_sqlitedbcursor.execute('attach database ? as ?', (attachscrapersqlitefile, asname or name))
        except sqlite3.Error, e:
            log.err(e)
            return {"error":"sqliteattach: sqlite3.Error: "+str(e)}
        return {"status":"attach succeeded"}


    def sqlitecommit(self):
        self.establishconnection(True)
        #signal.alarm(10)
        self.m_sqlitedbconn.commit()
        #signal.alarm(0)
        return {"status":"commit succeeded"}  # doesn't reach here if the signal fails


    def save_sqlite(self, unique_keys, data, swdatatblname):
        res = { }
        if type(data) == dict:
            data = [data]
        
        if not self.m_sqlitedbconn or swdatatblname not in self.sqlitesaveinfo:
            ssinfo = SqliteSaveInfo(self, swdatatblname)
            self.sqlitesaveinfo[swdatatblname] = ssinfo
            if not ssinfo.rebuildinfo() and data:
                ssinfo.buildinitialtable(data[0])
                ssinfo.rebuildinfo()
                res["tablecreated"] = swdatatblname
        else:
            ssinfo = self.sqlitesaveinfo[swdatatblname]
        
        nrecords = 0
        for ldata in data:
            newcols = ssinfo.newcolumns(ldata)
            if newcols:
                for i, kv in enumerate(newcols):
                    ssinfo.addnewcolumn(kv[0], kv[1])
                    res["newcolumn %d" % i] = "%s %s" % kv
                ssinfo.rebuildinfo()

            if nrecords == 0 and unique_keys:
                idxname, idxkeys = ssinfo.findclosestindex(unique_keys)
                if not idxname or idxkeys != set(unique_keys):
                    lres = ssinfo.makenewindex(idxname, unique_keys)
                    if "error" in lres:  
                        return lres
                    res.update(lres)
            
            lres = ssinfo.insertdata(ldata)
            if "error" in lres:  
                return lres
            nrecords += 1
        self.m_sqlitedbconn.commit()
        res["nrecords"] = nrecords
        res["status"] = 'Data record(s) inserted or replaced'
        return res


class SqliteSaveInfo:
    def __init__(self, database, swdatatblname):
        self.database = database
        self.swdatatblname = swdatatblname
        self.swdatakeys = [ ]
        self.swdatatypes = [  ]
        self.sqdatatemplate = ""

    def sqliteexecute(self, sqlquery, data=None):
        res = self.database.sqliteexecute(sqlquery, data, None, None)
        if "error" in res:
            log.msg("%s  %s" % (self.database.short_name, str(res)), logLevel=logging.WARNING)
        return res
    
    def rebuildinfo(self):
        if not self.sqliteexecute("select * from main.sqlite_master where name=?", (self.swdatatblname,))['data']:
            return False

        tblinfo = self.sqliteexecute("PRAGMA main.table_info(`%s`)" % self.swdatatblname)
            # there's a bug:  PRAGMA main.table_info(swdata) returns the schema for otherdatabase.swdata 
            # following an attach otherdatabase where otherdatabase has a swdata and main does not
        
        self.swdatakeys = [ a[1]  for a in tblinfo["data"] ]
        self.swdatatypes = [ a[2]  for a in tblinfo["data"] ]
        self.sqdatatemplate = "insert or replace into main.`%s` values (%s)" % (self.swdatatblname, ",".join(["?"]*len(self.swdatakeys)))
        return True
    
            
    def buildinitialtable(self, data):
        assert not self.swdatakeys
        coldef = self.newcolumns(data)
        assert coldef
        # coldef = coldef[:1]  # just put one column in; the rest could be altered -- to prove it's good
        scoldef = ", ".join(["`%s` %s" % col  for col in coldef])
                # used to just add date_scraped in, but without it can't create an empty table
        self.sqliteexecute("create table main.`%s` (%s)" % (self.swdatatblname, scoldef))
    
    def newcolumns(self, data):
        newcols = [ ]
        for k in data:
            if k not in self.swdatakeys:
                v = data[k]
                if v != None:
                    if k[-5:] == "_blob":
                        vt = "blob"  # coerced into affinity none
                    elif type(v) == int:
                        vt = "integer"
                    elif type(v) == float:
                        vt = "real"
                    else:
                        vt = "text"
                    newcols.append((k, vt))
        return newcols

    def addnewcolumn(self, k, vt):
        self.sqliteexecute("alter table main.`%s` add column `%s` %s" % (self.swdatatblname, k, vt))

    def findclosestindex(self, unique_keys):
        idxlist = self.sqliteexecute("PRAGMA main.index_list(`%s`)" % self.swdatatblname)  # [seq,name,unique]
        uniqueindexes = [ ]
        if 'error' in idxlist:
            return None, None
            
        for idxel in idxlist["data"]:
            if idxel[2]:
                idxname = idxel[1]
                idxinfo = self.sqliteexecute("PRAGMA main.index_info(`%s`)" % idxname) # [seqno,cid,name]
                idxset = set([ a[2]  for a in idxinfo["data"] ])
                idxoverlap = len(idxset.intersection(unique_keys))
                uniqueindexes.append((idxoverlap, idxname, idxset))
        
        if not uniqueindexes:
            return None, None
        uniqueindexes.sort()
        return uniqueindexes[-1][1], uniqueindexes[-1][2]

    # increment to next index number every time there is a change, and add the new index before dropping the old one.
    def makenewindex(self, idxname, unique_keys):
        istart = 0
        if idxname:
            mnum = re.search("(\d+)$", idxname)
            if mnum:
                istart = int(mnum.group(1))
        for i in range(10000):
            newidxname = "%s_index%d" % (self.swdatatblname, istart+i)
            if not self.sqliteexecute("select name from main.sqlite_master where name=?", (newidxname,))['data']:
                break
            
        res = { "newindex": newidxname }
        lres = self.sqliteexecute("create unique index `%s` on `%s` (%s)" % (newidxname, self.swdatatblname, ",".join(["`%s`"%k  for k in unique_keys])))
        if "error" in lres:  
            return lres
        if idxname:
            lres = self.sqliteexecute("drop index main.`%s`" % idxname)
            if "error" in lres:  
                if lres["error"] != 'sqlite3.Error: index associated with UNIQUE or PRIMARY KEY constraint cannot be dropped':
                    return lres
                log.msg("%s:  %s" % (self.database.short_name, str(lres)), logLevel=logging.INFO)
            res["droppedindex"] = idxname
        return res
            
    def insertdata(self, data):
        values = [ data.get(k)  for k in self.swdatakeys ]
        return self.sqliteexecute(self.sqdatatemplate, values)

