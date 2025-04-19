# ParentPlanner

A Python-based web scraper that collects and organizes family-friendly events from multiple sources, including King County Library System (KCLS) and ParentMap.

## Features

- Scrapes event details such as title, date, time, location, cost, description, and links.
- Stores event data locally using TinyDB.
- Avoids duplicate entries by checking existing events.
- Provides easy querying for free events.

## Sources

- [King County Library System (KCLS)](https://kcls.bibliocommons.com/)
- [ParentMap Weekender](https://www.parentmap.com/article/the-weekender)

## Technologies Used

- Python
- Playwright (for browser automation)
- BeautifulSoup (for HTML parsing)
- Requests (for HTTP requests)
- TinyDB (for lightweight JSON-based storage)
