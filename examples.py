import datetime
import scraperwiki_local_python as scraperwiki

scraperwiki.utils.httpresponseheader("Content-Type", "image/png")
html = scraperwiki.scrape("http://python.org/about")

scraperwiki.sqlite.save(unique_keys=["a"], data={"a":1, "bbb":"Hi there"})

scraperwiki.sqlite.select("* from swdata limit 10")

scraperwiki.sqlite.execute("insert into swdata values (?,?)", [datetime.datetime.now(),3])

scraperwiki.sqlite.save_var('last_page', 27)
print scraperwiki.sqlite.get_var('last_page')

print scraperwiki.sqlite.show_tables()

info = scraperwiki.sqlite.table_info(name="swdata")
for column in info:
    print column['name'], column['type']
