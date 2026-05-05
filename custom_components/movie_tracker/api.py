import logging
import aiohttp
import urllib.parse
import re
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

# CZDB API configuration
CZDB_BASE_URL = "https://api.czdb.cz"

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

class CSFDScraper:
    """Helper to get movie data using CZDB API."""

    @staticmethod
    async def search(query: str, tmdb_api_key: str = None) -> list:
        """Search for movies/series using CZDB API and TMDb for type detection."""
        url = f"{CZDB_BASE_URL}/search?q={urllib.parse.quote(query)}"
        try:
            async with aiohttp.ClientSession() as session:
                # Priority 1: Use TMDb Multi-search to identify types (if key available)
                type_map = {}
                if tmdb_api_key:
                    try:
                        t_url = f"https://api.themoviedb.org/3/search/multi?api_key={tmdb_api_key}&query={urllib.parse.quote(query)}&language=cs-CZ"
                        async with session.get(t_url, timeout=3) as t_resp:
                            if t_resp.status == 200:
                                t_data = await t_resp.json()
                                for item in t_data.get("results", []):
                                    name = item.get("title") or item.get("name")
                                    m_type = item.get("media_type")
                                    if name and m_type in ["tv", "movie"]:
                                        type_map[name.lower()] = m_type
                                        if item.get("original_title"): type_map[item["original_title"].lower()] = m_type
                                        if item.get("original_name"): type_map[item["original_name"].lower()] = m_type
                    except: pass

                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        _LOGGER.warning("CZDB search returned status %s", response.status)
                        return []
                    data = await response.json()
                    if not data or data.get("response") != "True":
                        return []
                    
                    results = []
                    for item in data.get("results", []):
                        title = item.get("nazev", "Neznámý název")
                        orig_title = item.get("original", "")
                        alt = item.get("alt_nazev", "")
                        
                        # Type detection from TMDb map first, then heuristics
                        t_type = type_map.get(title.lower()) or type_map.get(orig_title.lower())
                        
                        if t_type:
                            is_series = t_type == "tv"
                        else:
                            # Fallback Heuristics
                            is_series = (
                                "seriál" in title.lower() or 
                                "seriál" in alt.lower() or
                                "series" in alt.lower() or
                                any(x in title.lower() for x in [" - řada", " - série"])
                            )
                        
                        poster = item.get("obrazek_url") or item.get("imgo") or ""
                        
                        # Enhancement: Fetch better poster from TMDb
                        if tmdb_api_key:
                            try:
                                t_search_type = "tv" if is_series else "movie"
                                # Look for the best match in TMDb for poster
                                t_url = f"https://api.themoviedb.org/3/search/{t_search_type}?api_key={tmdb_api_key}&query={urllib.parse.quote(orig_title or title)}&language=cs-CZ"
                                async with session.get(t_url, timeout=2) as t_resp:
                                    if t_resp.status == 200:
                                        t_data = await t_resp.json()
                                        if t_data.get("results") and t_data["results"][0].get("poster_path"):
                                            poster = f"https://image.tmdb.org/t/p/w342{t_data['results'][0]['poster_path']}"
                            except: pass

                        # If poster is still from CZDB, use proxy
                        if poster and "pmgstatic.com" in poster:
                            poster = f"/api/movie_tracker/proxy_image?url={urllib.parse.quote(poster)}"

                        results.append({
                            "id": str(item.get("id")),
                            "csfd_id": str(item.get("csfd_id")),
                            "title": title,
                            "original_title": orig_title,
                            "year": str(item.get("rok", "N/A")),
                            "url": item.get("csfd_url"),
                            "poster": poster,
                            "type": "series" if is_series else "movie"
                        })
                    return results[:20]
        except Exception as e:
            _LOGGER.error("CZDB search failed: %s", e)
            return []

    @staticmethod
    async def get_details(movie_id: str, title: str = None, tmdb_api_key: str = None) -> dict:
        """Fetch details for a specific movie using CZDB API and optional TMDb."""
        if (not movie_id or "-" in movie_id or not movie_id.isdigit()) and title:
            _LOGGER.debug("ID missing or invalid for %s, searching by title", title)
            search_results = await CSFDScraper.search(title)
            if search_results:
                movie_id = search_results[0]["id"]
            else:
                return {}

        url = f"{CZDB_BASE_URL}/search?id={movie_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return {}
                    data = await response.json()
                    if not data or data.get("response") != "True" or not data.get("results"):
                        return {}
                    
                    item = data["results"][0]
                    title = item.get("nazev", "Neznámý název")
                    plot = item.get("plot", "")
                    
                    # Better series detection
                    is_series = (
                        item.get("typ") in ["series", "tvSeries", "seriál"] or 
                        "seriál" in plot.lower() or 
                        "seriálu" in plot.lower() or
                        item.get("cas") == "N/A"
                    )
                    
                    poster = item.get("obrazek_url") or item.get("imgo") or ""
                    if poster and "pmgstatic.com" in poster:
                        poster = f"/api/movie_tracker/proxy_image?url={urllib.parse.quote(poster)}"

                    details = {
                        "id": str(item.get("id")),
                        "csfd_id": str(item.get("csfd_id")),
                        "title": title,
                        "original_title": item.get("original", ""),
                        "year": str(item.get("rok", "N/A")),
                        "rating": item.get("hodnoceni", "N/A"),
                        "genres": [g.strip() for g in item.get("zanr", "").split(",")] if item.get("zanr") else [],
                        "description": item.get("plot", ""),
                        "poster": poster,
                        "origin": f"{item.get('zeme', 'N/A')} ({item.get('rok', 'N/A')})",
                        "url": item.get("csfd_url"),
                        "type": "series" if is_series else "movie",
                        "seasons": []
                    }

                    # Priority 1: TMDb for rich series data
                    if is_series and tmdb_api_key:
                        try:
                            # Search for the TV show
                            s_url = f"https://api.themoviedb.org/3/search/tv?api_key={tmdb_api_key}&query={urllib.parse.quote(details['original_title'] or title)}&language=cs-CZ"
                            async with session.get(s_url, timeout=5) as s_resp:
                                if s_resp.status == 200:
                                    s_data = await s_resp.json()
                                    if s_data.get("results"):
                                        tmdb_id = s_data["results"][0]["id"]
                                        # Get full details including seasons
                                        d_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={tmdb_api_key}&language=cs-CZ"
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
                                                            for ep in e_data.get("episodes", []):
                                                                ep_num = ep.get("episode_number")
                                                                ep_title = ep.get("name")
                                                                # Generate Hellspy link for episode
                                                                h_query = f"{details['title']} S{str(s_num).zfill(2)}E{str(ep_num).zfill(2)} cz dabing"
                                                                h_url = f"https://hellspy.to/?query={urllib.parse.quote(h_query)}"
                                                                
                                                                season_info["episodes"].append({
                                                                    "title": ep_title,
                                                                    "number": ep_num,
                                                                    "overview": ep.get("overview"),
                                                                    "url": h_url,
                                                                    "id": f"s{s_num}e{ep_num}"
                                                                })
                                                            details["seasons"].append(season_info)
                        except Exception as e:
                            _LOGGER.error("TMDb series fetch failed: %s", e)

                    # Priority 2: SerialZone Fallback (simplified)
                    if is_series and not details["seasons"]:
                        try:
                            ep_list = await SerialZoneScraper.get_episodes(title)
                            if ep_list:
                                details["seasons"].append({
                                    "name": "Všechny epizody",
                                    "episodes": [{"title": e["title"], "url": e["url"]} for e in ep_list]
                                })
                        except: pass

                    return details
        except Exception as e:
            _LOGGER.error("CZDB detail fetch failed: %s", e)
            return {}

async def get_hellspy_video_url(title: str, language: str = "CZ") -> str:
    """Search Hellspy and return the first result URL directly."""
    query = title
    if language == "CZ":
        query += " cz dabing"
    
    search_url = f"https://hellspy.to/?query={urllib.parse.quote(query)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    # Find the first link that contains '/video/'
                    first_video = soup.select_one("a[href*='/video/']")
                    if first_video:
                        href = first_video.get("href")
                        return f"https://hellspy.to{href}" if href.startswith("/") else href
    except Exception as e:
        _LOGGER.debug("Failed to scrape Hellspy: %s", e)
    
    return search_url

async def get_recommendations(watched_data: dict, wishlist_data: dict, tmdb_api_key: str = None) -> list:
    """Recommend movies based on watched history, user ratings, and TMDb."""
    genre_scores = {}
    last_favorites = []
    
    # Sort by rating and date to find top favorites
    sorted_watched = sorted(
        watched_data.values(), 
        key=lambda x: (int(x.get("user_rating", 0)), x.get("watched_at", "")), 
        reverse=True
    )
    
    for movie in sorted_watched:
        user_rating = int(movie.get("user_rating", 3)) # Default weight 3
        for genre in movie.get('genres', []):
            genre_scores[genre] = genre_scores.get(genre, 0) + user_rating
        
        if len(last_favorites) < 3 and movie.get("user_rating", 0) >= 4:
            last_favorites.append(movie)

    recommendations = []
    
    # Priority 1: TMDb Similar
    if tmdb_api_key and last_favorites:
        async with aiohttp.ClientSession() as session:
            for fav in last_favorites:
                try:
                    title = fav["title"]
                    is_series = fav.get("type") == "series"
                    t_type = "tv" if is_series else "movie"
                    
                    # Search to get ID
                    s_url = f"https://api.themoviedb.org/3/search/{t_type}?api_key={tmdb_api_key}&query={urllib.parse.quote(title)}&language=cs-CZ"
                    async with session.get(s_url, timeout=3) as resp:
                        if resp.status == 200:
                            s_data = await resp.json()
                            if s_data.get("results"):
                                tmdb_id = s_data["results"][0]["id"]
                                # Get recommendations
                                r_url = f"https://api.themoviedb.org/3/{t_type}/{tmdb_id}/recommendations?api_key={tmdb_api_key}&language=cs-CZ"
                                async with session.get(r_url, timeout=3) as r_resp:
                                    if r_resp.status == 200:
                                        r_data = await r_resp.json()
                                        for item in r_data.get("results", []):
                                            title = item.get("title") or item.get("name")
                                            # Check if already watched
                                            if any(w["title"].lower() == title.lower() for w in watched_data.values()):
                                                continue
                                                
                                            poster = f"https://image.tmdb.org/t/p/w342{item.get('poster_path')}" if item.get("poster_path") else ""
                                            recommendations.append({
                                                "id": f"tmdb_{item['id']}",
                                                "title": title,
                                                "year": (item.get("release_date") or item.get("first_air_date") or "N/A")[:4],
                                                "rating": f"{int(item.get('vote_average', 0) * 10)}%",
                                                "poster": poster,
                                                "type": "series" if t_type == "tv" else "movie",
                                                "description": item.get("overview", "")
                                            })
                                            if len(recommendations) >= 8: break
                except: continue
                if len(recommendations) >= 8: break

    # Priority 2: Wishlist genre matching (as fallback or addition)
    if len(recommendations) < 6:
        top_genre_names = [g[0] for g in sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:3]]
        for movie in wishlist_data.values():
            if any(g in top_genre_names for g in movie.get('genres', [])):
                if not any(r["title"] == movie["title"] for r in recommendations):
                    recommendations.append(movie)
            if len(recommendations) >= 10: break
                
    return recommendations[:10]
