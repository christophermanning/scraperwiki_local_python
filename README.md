# ScraperWiki Local Python

Use this if you want to develop and test a ScraperWiki Python scraper locally. The code in the scraperwiki directory is a subset of the [ScraperWiki repository](https://bitbucket.org/ScraperWiki/scraperwiki/src). Using the ScraperWiki source to emulate the fuctions was the main goal of this project.

## Features

* Saves data to local SQLite database
* Scraped pages are cached to filesystem
* Uses ScraperWiki source to emulate functions

## Usage
     
Download the scraperwiki_local_python folder into your working directory and add `import scraperwiki_local_python as scraperwiki` to your scraper (be sure to remove the "scraperwiki_local_python as " part before saving your scraper at ScraperWiki)

The database and the page cache will be saved in a folder with the same name as your python script in your working directory.
        
## License

GPLv3 
[Same as ScraperWiki](https://bitbucket.org/ScraperWiki/scraperwiki/src/ed6ad9e56aa0/LICENSE.txt)
