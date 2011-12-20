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

url = "http://www.madingley.org/uploaded/Hansard_08.07.2010.pdf"
pdfdata = scraperwiki.scrape(url)
print "The pdf file has %d bytes" % len(pdfdata)

xmldata = scraperwiki.pdftoxml(pdfdata)
print "After converting to xml it has %d bytes" % len(xmldata)
print "The first 2000 characters are: ", xmldata[:2000]

print scraperwiki.geo.gb_postcode_to_latlng('ME7 9AA')

print scraperwiki.utils.swimport("scraperwiki")