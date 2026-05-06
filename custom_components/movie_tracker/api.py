import logging
import aiohttp
import urllib.parse
import re
import asyncio
import random
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

# CZDB API configuration
CZDB_BASE_URL = "https://api.czdb.cz"

async def search_movies(query: str, tmdb_api_key: str = None) -> list:
    """Search for movies and TV shows using TMDb."""
    if not tmdb_api_key: return []
    url = f"https://api.themoviedb.org/3/search/multi?api_key={tmdb_api_key}&query={urllib.parse.quote(query)}&language=cs-CZ"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = []
                for item in data.get("results", []):
                    m_type = item.get("media_type")
                    if m_type not in ["movie", "tv"]: continue
                    title = item.get("title") or item.get("name")
                    poster_path = item.get("poster_path")
                    poster = f"/api/movie_tracker/proxy_image?url={urllib.parse.quote('https://image.tmdb.org/t/p/w185' + poster_path)}" if poster_path else ""
                    results.append({
                        "id": str(item["id"]),
                        "title": title,
                        "year": (item.get("release_date") or item.get("first_air_date") or "N/A")[:4],
                        "type": "series" if m_type == "tv" else "movie",
                        "poster": poster
                    })
                return results
    return []

class SerialZoneScraper:
    """Helper to scrape episodes from SerialZone.cz."""
    BASE_URL = "https://www.serialzone.cz"

    @staticmethod
    async def get_episodes(title: str) -> list:
        """Search for a series and return its episodes."""
        search_url = f"{SerialZoneScraper.BASE_URL}/hledani/?co={urllib.parse.quote(title)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, allow_redirects=True, timeout=10) as response:
                    final_url = str(response.url)
                    
                    if "/serial/" not in final_url:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        link = soup.find("a", href=re.compile(r"^/serial/"))
                        if link:
                            final_url = SerialZoneScraper.BASE_URL + link["href"]
                        else:
                            return []
                    
                    if not final_url.endswith("/epizody/"):
                        if final_url.endswith("/"):
                            final_url += "epizody/"
                        else:
                            final_url += "/epizody/"

                    async with session.get(final_url, headers=headers, timeout=10) as ep_resp:
                        if ep_resp.status != 200:
                            return []
                        
                        html = await ep_resp.text()
                        soup = BeautifulSoup(html, "html.parser")
                        episodes = []
                        
                        for container in soup.select("div.subs"):
                            link = container.select_one("a.suname")
                            if link:
                                ep_title = link.text.strip()
                                ep_url = link.get("href")
                                if not ep_url.startswith("http"):
                                    ep_url = SerialZoneScraper.BASE_URL + ep_url
                                
                                episodes.append({
                                    "title": ep_title,
                                    "url": ep_url
                                })
                        return episodes
        except Exception as e:
            _LOGGER.warning("SerialZone scrape failed: %s", e)
            return []

async def get_details(title: str, is_series: bool = False, tmdb_api_key: str = None) -> dict:
    """Fetch movie/series details from multiple sources."""
    details = {
        "title": title,
        "type": "series" if is_series else "movie",
        "poster": "",
        "rating": "",
        "year": "",
        "description": "",
        "genres": [],
        "origin": "",
        "seasons": [],
        "hellspy_url": f"https://hellspy.to/?query={urllib.parse.quote(title + (' cz dabing' if not is_series else ''))}"
    }

    async with aiohttp.ClientSession() as session:
        try:
            # Priority 1: CZDB (for local relevance)
            czdb_url = f"{CZDB_BASE_URL}/search?q={urllib.parse.quote(title)}"
            async with session.get(czdb_url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        # Find best match
                        item = data[0]
                        details.update({
                            "title": item.get("title", title),
                            "rating": item.get("rating", ""),
                            "year": item.get("year", ""),
                            "description": item.get("description", ""),
                            "origin": item.get("origin", ""),
                        })
                        if item.get("genres"):
                            details["genres"] = item["genres"]
                        
                        # Get TMDb posters and seasons if possible
                        tmdb_id = None
                        q_type = "tv" if is_series else "movie"
                        s_url = f"https://api.themoviedb.org/3/search/{q_type}?api_key={tmdb_api_key}&query={urllib.parse.quote(title)}&language=cs-CZ"
                        async with session.get(s_url, timeout=5) as s_resp:
                            if s_resp.status == 200:
                                s_data = await s_resp.json()
                                if s_data.get("results"):
                                    tmdb_id = s_data["results"][0]["id"]
                                    d_url = f"https://api.themoviedb.org/3/{q_type}/{tmdb_id}?api_key={tmdb_api_key}&language=cs-CZ"
                                    async with session.get(d_url, timeout=5) as d_resp:
                                        if d_resp.status == 200:
                                            d_data = await d_resp.json()
                                            if d_data.get("poster_path"):
                                                details["poster"] = f"https://image.tmdb.org/t/p/w780{d_data['poster_path']}"
                                            
                                            for season in d_data.get("seasons", []):
                                                s_num = season.get("season_number")
                                                if s_num == 0: continue # Skip specials
                                                
                                                # Get episodes for this season
                                                e_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{s_num}?api_key={tmdb_api_key}&language=cs-CZ"
                                                async with session.get(e_url, timeout=5) as e_resp:
                                                    if e_resp.status == 200:
                                                        e_data = await e_resp.json()
                                                        season_info = {
                                                            "name": season.get("name") or f"{s_num}. řada",
                                                            "episodes": []
                                                        }
                                                        # Prepare tasks for direct Hellspy links for episodes
                                                        ep_tasks = []
                                                        for ep in e_data.get("episodes", []):
                                                            ep_num = ep.get("episode_number")
                                                            h_query = f"{details['title']} S{str(s_num).zfill(2)}E{str(ep_num).zfill(2)} cz dabing"
                                                            ep_tasks.append((ep, h_query))
                                                        
                                                        sem = asyncio.Semaphore(2)
                                                        async def get_direct_ep(e, q):
                                                            async with sem:
                                                                await asyncio.sleep(0.5)
                                                                return e, await get_hellspy_video_url(q, "CZ")
                                                        
                                                        ep_results = await asyncio.gather(*[get_direct_ep(e, q) for e, q in ep_tasks])
                                                        for ep, h_url in ep_results:
                                                            season_info["episodes"].append({
                                                                "title": ep.get("name"),
                                                                "number": ep.get("episode_number"),
                                                                "overview": ep.get("overview"),
                                                                "url": h_url,
                                                                "id": f"s{s_num}e{ep.get('episode_number')}"
                                                            })
                                                        details["seasons"].append(season_info)
                        
                        # Smarter hellspy_url for series: go to S01E01 by default
                        if is_series and details.get("seasons"):
                            first_s = details["seasons"][0]
                            if first_s.get("episodes"):
                                ep1 = first_s["episodes"][0]
                                s_num = first_s.get("number") or 1
                                ep_num = ep1.get("number") or 1
                                q = f"{details['title']} S{str(s_num).zfill(2)}E{str(ep_num).zfill(2)} cz dabing"
                                details["hellspy_url"] = await get_hellspy_video_url(q, "CZ")

                        return details
        except Exception as e:
            _LOGGER.error("Fetch failed: %s", e)
            return {}
    return details

async def get_hellspy_video_url(title: str, language: str = "CZ") -> str:
    """Search Hellspy and return the first result URL directly."""
    query = title
    if language == "CZ" and "cz dabing" not in title.lower():
        query += " cz dabing"
    
    # Try to extract SXXEXX if present
    ep_pattern = re.search(r"S(\d+)E(\d+)", title, re.I)
    ep_str = ep_pattern.group(0).upper() if ep_pattern else None

    search_url = f"https://hellspy.to/?query={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8"
    }
    try:
        # Add a small jitter to avoid bot detection
        await asyncio.sleep(random.uniform(0.1, 0.5))
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    video_links = []
                    for link in soup.select("a"):
                        href = link.get("href", "")
                        if not href: continue
                        
                        text = link.text.strip().upper()
                        # Pattern matching for videos
                        if any(p in href for p in ["/video/", "/stahuj/", "/file/", "/download/"]):
                            full_url = f"https://hellspy.to{href}" if href.startswith("/") else href
                            # If we searched for a specific episode, prioritize it in the title
                            if ep_str and ep_str in text:
                                return full_url
                            video_links.append(full_url)
                    
                    if video_links:
                        return video_links[0]
    except Exception as e:
        _LOGGER.debug("Failed to scrape Hellspy: %s", e)
    
    return search_url

async def get_discover(tmdb_api_key: str, media_type: str = "movie", genre_id: str = None, year: str = None, min_rating: float = 0) -> list:
    """Discover movies or TV shows based on filters using TMDb."""
    url = f"https://api.themoviedb.org/3/discover/{media_type}?api_key={tmdb_api_key}&language=cs-CZ&sort_by=popularity.desc"
    if genre_id: url += f"&with_genres={genre_id}"
    if year: url += f"&primary_release_year={year}" if media_type == "movie" else f"&first_air_date_year={year}"
    if min_rating: url += f"&vote_average.gte={min_rating}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = []
                for item in data.get("results", []):
                    title = item.get("title") or item.get("name")
                    poster_path = item.get("poster_path")
                    poster = f"/api/movie_tracker/proxy_image?url={urllib.parse.quote('https://image.tmdb.org/t/p/w342' + poster_path)}" if poster_path else ""
                    results.append({
                        "id": f"tmdb_{item['id']}",
                        "title": title,
                        "year": (item.get("release_date") or item.get("first_air_date") or "N/A")[:4],
                        "rating": f"{int(item.get('vote_average', 0) * 10)}%",
                        "poster": poster,
                        "type": "series" if media_type == "tv" else "movie",
                        "description": item.get("overview", "")
                    })
                return results
    return []

async def get_recommendations(watched_data: dict, wishlist_data: dict, tmdb_api_key: str, not_interested: dict = None) -> list:
    """Generate recommendations based on history, ratings and wishlist."""
    import time
    now = time.time()
    # Filter valid not_interested IDs
    ni_ids = set()
    if not_interested:
        ni_ids = {m_id for m_id, expire in not_interested.items() if expire > now}

    # 1. Get wishlist items
    wishlist = list(wishlist_data.values())
    
    # Priority seeds: Top rated (4-5), Wishlist items, and Recent
    top_rated = [m for m in watched_data.values() if int(m.get("user_rating", 0)) >= 4]
    recent = sorted(watched_data.values(), key=lambda x: x.get("watched_at", ""), reverse=True)[:5]
    
    # Mix them up for variety
    seed_pool = {m["id"]: m for m in top_rated + wishlist + recent}.values()
    import random
    seeds = random.sample(list(seed_pool), min(len(seed_pool), 5)) if seed_pool else []

    recommendations = []
    if tmdb_api_key:
        async with aiohttp.ClientSession() as session:
            # A. From seeds
            for seed in seeds:
                try:
                    title = seed["title"]
                    t_type = "tv" if seed.get("type") == "series" else "movie"
                    s_url = f"https://api.themoviedb.org/3/search/{t_type}?api_key={tmdb_api_key}&query={urllib.parse.quote(title)}&language=cs-CZ"
                    async with session.get(s_url, timeout=3) as resp:
                        if resp.status == 200:
                            s_data = await resp.json()
                            if s_data.get("results"):
                                tmdb_id = s_data["results"][0]["id"]
                                r_url = f"https://api.themoviedb.org/3/{t_type}/{tmdb_id}/recommendations?api_key={tmdb_api_key}&language=cs-CZ"
                                async with session.get(r_url, timeout=3) as r_resp:
                                    if r_resp.status == 200:
                                        r_data = await r_resp.json()
                                        for item in r_data.get("results", [])[:3]:
                                            r_id = f"tmdb_{item['id']}"
                                            if r_id in ni_ids: continue
                                            r_title = item.get("title") or item.get("name")
                                            if r_title.lower() in [w["title"].lower() for w in watched_data.values()]: continue
                                            if r_title.lower() in [w["title"].lower() for w in wishlist_data.values()]: continue
                                            poster_path = item.get("poster_path")
                                            poster = f"/api/movie_tracker/proxy_image?url={urllib.parse.quote('https://image.tmdb.org/t/p/w342' + poster_path)}" if poster_path else ""
                                            recommendations.append({
                                                "id": r_id,
                                                "title": r_title,
                                                "year": (item.get("release_date") or item.get("first_air_date") or "N/A")[:4],
                                                "rating": f"{int(item.get('vote_average', 0) * 10)}%",
                                                "poster": poster,
                                                "type": "series" if t_type == "tv" else "movie",
                                                "description": item.get("overview", "")
                                            })
                except: continue

            # B. Trending
            t_url = f"https://api.themoviedb.org/3/trending/all/week?api_key={tmdb_api_key}&language=cs-CZ"
            try:
                async with session.get(t_url, timeout=3) as resp:
                    if resp.status == 200:
                        t_data = await resp.json()
                        for item in t_data.get("results", [])[:10]:
                            r_id = f"tmdb_{item['id']}"
                            if r_id in ni_ids: continue
                            r_title = item.get("title") or item.get("name")
                            if r_title.lower() in [w["title"].lower() for w in watched_data.values()]: continue
                            if r_title.lower() in [w["title"].lower() for w in wishlist_data.values()]: continue
                            poster_path = item.get("poster_path")
                            poster = f"/api/movie_tracker/proxy_image?url={urllib.parse.quote('https://image.tmdb.org/t/p/w342' + poster_path)}" if poster_path else ""
                            recommendations.append({
                                "id": r_id,
                                "title": r_title,
                                "year": (item.get("release_date") or item.get("first_air_date") or "N/A")[:4],
                                "rating": f"{int(item.get('vote_average', 0) * 10)}%",
                                "poster": poster,
                                "type": item.get("media_type", "movie"),
                                "description": item.get("overview", "")
                            })
            except: pass

    random.shuffle(recommendations)
    seen_ids = set()
    unique_recs = []
    for r in recommendations:
        if r["id"] not in seen_ids:
            unique_recs.append(r)
            seen_ids.add(r["id"])
    return unique_recs[:15]

class CSFDScraper:
    """Compatibility class for older versions that used CSFDScraper."""
    @staticmethod
    async def search(query, tmdb_api_key=None):
        return await search_movies(query, tmdb_api_key)
    
    @staticmethod
    async def get_details(movie_id, title=None, tmdb_api_key=None):
        # Handle cases where movie_id was passed as the first argument
        search_title = title if title else movie_id
        return await get_details(search_title, tmdb_api_key=tmdb_api_key)
