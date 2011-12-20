# ScraperWiki Local Python

Use this if you want to locally develop and test a Python ScraperWiki scraper. The code in the scraperwiki_local_python/scraperwiki directory is a subset of the [ScraperWiki repository](https://bitbucket.org/ScraperWiki/scraperwiki/src). 

Using the ScraperWiki source to emulate the functions was the main goal of this project.

## Features

* Saves data to local SQLite database
* Scraped pages are cached to filesystem
* Supports all of the functions at https://scraperwiki.com/docs/python/python_help_documentation/
* Uses the ScraperWiki source to emulate functions

## Usage
     
Download the scraperwiki_local_python folder into your working directory and, in your scraper, replace the `import scraperwiki` line with `import scraperwiki_local_python as scraperwiki` (be sure to revert this change and replace `import scraperwiki_local_python as scraperwiki` with `import scraperwiki` before saving your scraper at ScraperWiki)

The SQLite database and the scraped page cache will be saved to a folder in your working directory. E.g. Running `python examples.py` will create an examples_data folder with page cache folder and a defaultdb.sqlite database inside of it.

## License

GPLv3 
[Same as ScraperWiki](https://bitbucket.org/ScraperWiki/scraperwiki/src/ed6ad9e56aa0/LICENSE.txt)
