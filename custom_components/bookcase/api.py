import aiohttp
import logging

_LOGGER = logging.getLogger(__name__)

async def fetch_book_metadata(isbn: str):
    """Fetch book metadata from multiple sources (Open Library, Google Books, Knihovny.cz)."""
    async with aiohttp.ClientSession() as session:
        # 1. Try Open Library
        ol_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        try:
            async with session.get(ol_url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    key = f"ISBN:{isbn}"
                    if key in data:
                        _LOGGER.info("Book found in Open Library")
                        b = data[key]
                        return {
                            "isbn": isbn,
                            "title": b.get("title", "Unknown"),
                            "subtitle": b.get("subtitle"),
                            "authors": [a.get("name") for a in b.get("authors", [])],
                            "publishers": [p.get("name") for p in b.get("publishers", [])],
                            "publish_date": b.get("publish_date"),
                            "languages": [l.get("name") for l in b.get("languages", [])],
                            "cover_url": b.get("cover", {}).get("large"),
                            "pages": b.get("number_of_pages"),
                            "url": b.get("url"),
                            "subjects": [s.get("name") for s in b.get("subjects", [])[:5]]
                        }
        except Exception: pass

        # 2. Try Google Books
        gb_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        try:
            async with session.get(gb_url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("totalItems", 0) > 0:
                        _LOGGER.info("Book found in Google Books")
                        i = data["items"][0]["volumeInfo"]
                        cover_url = i.get("imageLinks", {}).get("thumbnail")
                        if cover_url and cover_url.startswith("http://"):
                            cover_url = cover_url.replace("http://", "https://")
                        return {
                            "isbn": isbn,
                            "title": i.get("title", "Unknown"),
                            "subtitle": i.get("subtitle"),
                            "authors": i.get("authors", ["Neznámý autor"]),
                            "publishers": [i.get("publisher")] if i.get("publisher") else [],
                            "publish_date": i.get("publishedDate"),
                            "languages": [i.get("language")],
                            "cover_url": cover_url,
                            "pages": i.get("pageCount"),
                            "url": i.get("infoLink"),
                            "subjects": i.get("categories", [])
                        }
        except Exception: pass

        # 3. Try Knihovny.cz (Great for Czech books)
        kn_url = f"https://www.knihovny.cz/api/v1/search?q=isbn:{isbn}"
        try:
            async with session.get(kn_url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("resultCount", 0) > 0:
                        _LOGGER.info("Book found in Knihovny.cz")
                        r = data["records"][0]
                        return {
                            "isbn": isbn,
                            "title": r.get("title", "Unknown"),
                            "authors": list(r.get("authors", {}).get("primary", {}).keys()),
                            "publishers": list(r.get("authors", {}).get("secondary", {}).keys()),
                            "publish_date": r.get("publicationDate"),
                            "languages": r.get("languages", []),
                            "cover_url": f"https://www.knihovny.cz/Cover/Show?id={r.get('id')}&size=large",
                            "pages": None,
                            "url": f"https://www.knihovny.cz/Record/{r.get('id')}",
                            "subjects": [s[0] for s in r.get("subjects", [])[:5]]
                        }
        except Exception: pass

    _LOGGER.warning("Book with ISBN %s not found in any database", isbn)
    return None
