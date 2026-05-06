from __future__ import annotations

import logging
import os
import time
import uuid
import asyncio
import urllib.parse
from datetime import datetime

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
import homeassistant.util.dt as dt_util

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, EVENT_MOVIES_UPDATED
from .api import search_movies, get_details, get_hellspy_video_url, get_recommendations

from aiohttp import web

_LOGGER = logging.getLogger(__name__)

class DataView(HomeAssistantView):
    url = "/api/movie_tracker/data"
    name = "api:movie_tracker:data"
    requires_auth = True

    def __init__(self, data, tmdb_key):
        self._data = data
        self._tmdb_key = tmdb_key

    async def get(self, request):
        try:
            from .api import get_recommendations
            recommendations = await get_recommendations(self._data["watched"], self._data["wishlist"], tmdb_api_key=self._tmdb_key, not_interested=self._data.get("not_interested", {}))
            return web.json_response({
                "watched": self._data["watched"],
                "wishlist": self._data["wishlist"],
                "settings": self._data["settings"],
                "not_interested": self._data.get("not_interested", {}),
                "recommendations": recommendations
            })
        except Exception as e:
            _LOGGER.error("Error in DataView: %s", e, exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

class SearchView(HomeAssistantView):
    url = "/api/movie_tracker/search"
    name = "api:movie_tracker:search"
    requires_auth = True
    def __init__(self, tmdb_key):
        self._tmdb_key = tmdb_key
    async def get(self, request):
        query = request.query.get("q", "")
        if not query: return web.json_response([])
        from .api import search_movies
        results = await search_movies(query, tmdb_api_key=self._tmdb_key)
        return web.json_response(results)

class ProxyImageView(HomeAssistantView):
    url = "/api/movie_tracker/proxy_image"
    name = "api:movie_tracker:proxy_image"
    requires_auth = False
    async def get(self, request):
        import hashlib
        image_url = request.query.get("url")
        if not image_url: return web.Response(status=400)
        cache_dir = os.path.join(os.path.dirname(__file__), "www", "posters")
        os.makedirs(cache_dir, exist_ok=True)
        url_hash = hashlib.md5(image_url.encode()).hexdigest()
        ext = image_url.split(".")[-1].split("?")[0] if "." in image_url else "jpg"
        cache_path = os.path.join(cache_dir, f"{url_hash}.{ext}")
        if os.path.isfile(cache_path): return web.FileResponse(cache_path)
        headers = {"Referer": "https://www.csfd.cz/", "User-Agent": "Mozilla/5.0"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        def save_file():
                            with open(cache_path, "wb") as f: f.write(content)
                        await self.hass.async_add_executor_job(save_file)
                        return web.Response(body=content, content_type=resp.content_type)
        except Exception as e: _LOGGER.error("Proxy image failed: %s", e)
        return web.Response(status=404)

class DiscoverView(HomeAssistantView):
    url = "/api/movie_tracker/discover"
    name = "api:movie_tracker:discover"
    requires_auth = True
    def __init__(self, tmdb_key):
        self._tmdb_key = tmdb_key
    async def get(self, request):
        from .api import get_discover
        media_type = request.query.get("type", "movie")
        genre = request.query.get("genre")
        year = request.query.get("year")
        try: min_rating = float(request.query.get("rating", 0))
        except: min_rating = 0
        results = await get_discover(self._tmdb_key, media_type, genre, year, min_rating)
        return web.json_response(results)

class DetailView(HomeAssistantView):
    url = "/api/movie_tracker/detail"
    name = "api:movie_tracker:detail"
    requires_auth = True
    def __init__(self, data, tmdb_key):
        self._data = data
        self._tmdb_key = tmdb_key
    async def get(self, request):
        movie_id = request.query.get("id", "")
        title = request.query.get("title", "")
        if not movie_id and not title: return web.json_response({"error": "Missing ID or Title"}, status=400)
        try:
            from .api import get_details, get_hellspy_video_url
            details = await get_details(title, tmdb_api_key=self._tmdb_key)
            if details:
                lang = self._data.get("settings", {}).get("language", "CZ")
                query_text = details.get("title", title)
                details["hellspy_url"] = await get_hellspy_video_url(query_text, lang)
                return web.json_response(details)
            return web.json_response({"error": "Movie not found"}, status=404)
        except Exception as e:
            _LOGGER.error("Error in DetailView: %s", e, exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

# --- HTTP Views ---
class MovieTrackerPanelJsView(HomeAssistantView):
    """Serve the frontend panel JavaScript."""
    url = "/movie_tracker_static/panel.js"
    name = "api:movie_tracker:panel"
    requires_auth = False

    async def get(self, request):
        from aiohttp import web
        path = os.path.join(os.path.dirname(__file__), "www", "panel.js")
        if not os.path.isfile(path):
            return web.Response(status=404, text="panel.js not found")
        return web.FileResponse(path, headers={"Cache-Control": "no-cache"})

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up Movie Tracker from a config entry."""
    try:
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        data = await store.async_load() or {}
        
        # Ensure structure
        data.setdefault("watched", {})
        data.setdefault("wishlist", {})
        data.setdefault("settings", {"language": "CZ"})
        
        tmdb_key = entry.data.get("tmdb_api_key", "")
        
        # Store data for views
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = {
            "data": data,
            "tmdb_key": tmdb_key,
            "store": store
        }

        # Register views
        views = [
            MovieTrackerPanelJsView(),
            DataView(data, tmdb_key),
            SearchView(tmdb_key),
            DetailView(data, tmdb_key),
            ProxyImageView(),
            DiscoverView(tmdb_key)
        ]
        for view in views:
            try:
                hass.http.register_view(view)
            except Exception:
                pass # Already registered

    except Exception as exc:
        _LOGGER.error("Error setting up Movie Tracker entry: %s", exc, exc_info=True)
        return False

    # --- Services ---
    async def handle_movie_action(call: ServiceCall):
        action = call.data.get("action")
        movie = call.data.get("movie", {})
        movie_id = str(movie.get("id") or movie.get("csfd_id") or uuid.uuid4())
        
        if action == "not_interested":
            import time
            if "not_interested" not in data:
                data["not_interested"] = {}
            # Hide for 30 days
            data["not_interested"][movie_id] = time.time() + (30 * 24 * 3600)
        elif action == "watch":
            # Get existing data if possible to preserve seasons/details
            existing = data["watched"].get(movie_id) or data["wishlist"].get(movie_id)
            if existing:
                movie = {**movie, **existing}
            
            data["watched"][movie_id] = movie
            data["watched"][movie_id]["watched_at"] = dt_util.now().isoformat()
            data["wishlist"].pop(movie_id, None)
            
        elif action == "wishlist":
            data["wishlist"][movie_id] = movie
            data["wishlist"][movie_id]["added_at"] = dt_util.now().isoformat()
            
        elif action == "delete_watched":
            data["watched"].pop(movie_id, None)
            
        elif action == "delete_wishlist":
            data["wishlist"].pop(movie_id, None)
            
        elif action == "watch_episode":
            ep_id = str(call.data.get("episode_id"))
            # Get movie from either list
            target = data["watched"].get(movie_id) or data["wishlist"].get(movie_id)
            if not target:
                target = movie
                data["watched"][movie_id] = target

            if "watched_episodes" not in target: target["watched_episodes"] = {}
            if isinstance(target["watched_episodes"], list): target["watched_episodes"] = {} # Migration
            
            target["watched_episodes"][ep_id] = target["watched_episodes"].get(ep_id, {})
            target["watched_episodes"][ep_id]["watched"] = True
            
            # If we watch an episode, ensure series is in watched list
            if movie_id not in data["watched"]:
                data["watched"][movie_id] = target
                data["wishlist"].pop(movie_id, None)

        elif action == "rate_episode":
            ep_id = str(call.data.get("episode_id"))
            rating = call.data.get("rating")
            target = data["watched"].get(movie_id) or data["wishlist"].get(movie_id)
            if not target:
                target = movie
                data["watched"][movie_id] = target

            if "watched_episodes" not in target: target["watched_episodes"] = {}
            if isinstance(target["watched_episodes"], list): target["watched_episodes"] = {}
            
            target["watched_episodes"][ep_id] = target["watched_episodes"].get(ep_id, {})
            target["watched_episodes"][ep_id]["rating"] = rating
            target["watched_episodes"][ep_id]["watched"] = True
            
            if movie_id not in data["watched"]:
                data["watched"][movie_id] = target
                data["wishlist"].pop(movie_id, None)
        
        elif action == "watch_season":
            season_num = call.data.get("season_num")
            episodes = call.data.get("episodes", []) # List of episode IDs in this season
            target = data["watched"].get(movie_id) or data["wishlist"].get(movie_id) or movie
            
            if "watched_episodes" not in target: target["watched_episodes"] = {}
            for ep_id in episodes:
                eid = str(ep_id)
                target["watched_episodes"][eid] = target["watched_episodes"].get(eid, {})
                target["watched_episodes"][eid]["watched"] = True
            
            if movie_id not in data["watched"]:
                data["watched"][movie_id] = target
                data["wishlist"].pop(movie_id, None)

        elif action == "rate":
            rating = call.data.get("rating")
            target = data["watched"].get(movie_id) or data["wishlist"].get(movie_id)
            if not target:
                target = movie
                data["watched"][movie_id] = target
                data["wishlist"].pop(movie_id, None)
            
            target["user_rating"] = rating
            if movie_id not in data["watched"]:
                data["watched"][movie_id] = target
                data["wishlist"].pop(movie_id, None)

        elif action == "update_settings":
            data["settings"].update(call.data.get("settings", {}))
        
        await _save()
        hass.bus.async_fire(EVENT_MOVIES_UPDATED)

    if not hass.services.has_service(DOMAIN, "movie_action"):
        hass.services.async_register(DOMAIN, "movie_action", handle_movie_action)

    # --- Register Panel ---
    if "movie-tracker" not in hass.data.get("frontend_panels", {}):
        try:
            from homeassistant.components.frontend import async_register_built_in_panel
            async_register_built_in_panel(
                hass,
                component_name="custom",
                sidebar_title="Filmotéka",
                sidebar_icon="mdi:movie-roll",
                frontend_url_path="movie-tracker",
                config={
                    "_panel_custom": {
                        "name": "movie-tracker-panel",
                        "module_url": f"/movie_tracker_static/panel.js?v={int(time.time())}",
                    }
                },
                require_admin=False,
            )
        except Exception as exc:
            _LOGGER.error("Failed to register movie tracker panel: %s", exc)

    # Register platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload a config entry."""
    hass.services.async_remove(DOMAIN, "movie_action")
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
