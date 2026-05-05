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
from homeassistant.components.http import HomeAssistantView
import homeassistant.util.dt as dt_util

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, EVENT_MOVIES_UPDATED
from .api import CSFDScraper, get_hellspy_video_url, get_recommendations

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the component from configuration.yaml."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up Movie Tracker from a config entry."""
    
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {}
    
    # Ensure structure
    data.setdefault("watched", {})  # id -> movie_details
    data.setdefault("wishlist", {}) # id -> movie_details
    data.setdefault("history", [])  # list of watch events
    data.setdefault("settings", {"language": "CZ"}) # User settings
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = data

    async def _save():
        await store.async_save(data)
        hass.bus.async_fire(EVENT_MOVIES_UPDATED)

    # --- HTTP Views ---
    
    class PanelJsView(HomeAssistantView):
        url = "/movie_tracker_static/panel.js"
        name = "api:movie_tracker:panel"
        requires_auth = False
        async def get(self, request):
            from aiohttp import web
            path = os.path.join(os.path.dirname(__file__), "www", "panel.js")
            if not os.path.isfile(path):
                return web.Response(status=404, text="panel.js not found")
            return web.FileResponse(path, headers={"Cache-Control": "no-cache"})

    class DataView(HomeAssistantView):
        url = "/api/movie_tracker/data"
        name = "api:movie_tracker:data"
        requires_auth = True
        async def get(self, request):
            from aiohttp import web
            # Add Hellspy links and recommendations dynamically if needed, 
            # or just serve raw data
            # Get recommendations based on watched history
            tmdb_key = entry.data.get("tmdb_api_key", "")
            recommendations = await get_recommendations(data["watched"], data["wishlist"], tmdb_api_key=tmdb_key)
            
            return web.json_response({
                "watched": data["watched"],
                "wishlist": data["wishlist"],
                "settings": data["settings"],
                "recommendations": recommendations
            })

    class SearchView(HomeAssistantView):
        url = "/api/movie_tracker/search"
        name = "api:movie_tracker:search"
        requires_auth = True
        async def get(self, request):
            from aiohttp import web
            query = request.query.get("q", "")
            if not query:
                return web.json_response([])
            results = await CSFDScraper.search(query, tmdb_api_key=tmdb_key)
            return web.json_response(results)

    tmdb_key = entry.data.get("tmdb_api_key", "")
    
    class ProxyImageView(HomeAssistantView):
        url = "/api/movie_tracker/proxy_image"
        name = "api:movie_tracker:proxy_image"
        requires_auth = False # Allow browser to fetch images without auth token in URL if needed, but better to keep it for security
        async def get(self, request):
            import aiohttp
            image_url = request.query.get("url")
            if not image_url:
                return web.Response(status=400)
            
            headers = {
                "Referer": "https://www.csfd.cz/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            return web.Response(body=content, content_type=resp.content_type)
            except Exception as e:
                _LOGGER.error("Proxy image failed: %s", e)
            return web.Response(status=404)

    class DetailView(HomeAssistantView):
        url = "/api/movie_tracker/detail"
        name = "api:movie_tracker:detail"
        requires_auth = True
        async def get(self, request):
            from aiohttp import web
            movie_id = request.query.get("id", "")
            title = request.query.get("title", "")
            if not movie_id and not title:
                return web.json_response({"error": "Missing ID or Title"}, status=400)
            
            try:
                details = await CSFDScraper.get_details(movie_id, title, tmdb_api_key=tmdb_key)
                if details:
                    lang = data.get("settings", {}).get("language", "CZ")
                    # Get direct video link from Hellspy
                    query_text = details.get("title", title)
                    details["hellspy_url"] = await get_hellspy_video_url(query_text, lang)
                    return web.json_response(details)
                return web.json_response({"error": "Movie not found"}, status=404)
            except Exception as e:
                _LOGGER.error("Error in DetailView: %s", e, exc_info=True)
                return web.json_response({"error": str(e)}, status=500)

    hass.http.register_view(PanelJsView())
    hass.http.register_view(DataView())
    hass.http.register_view(SearchView())
    hass.http.register_view(DetailView())
    hass.http.register_view(ProxyImageView())

    # --- Services ---

    async def handle_movie_action(call: ServiceCall):
        action = call.data.get("action")
        movie = call.data.get("movie") # dict with details
        if not action or not movie:
            return

        movie_id = movie.get("id") or str(uuid.uuid4())
        
        if action == "watch":
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
            ep_id = call.data.get("episode_id")
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
            ep_id = call.data.get("episode_id")
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
            target = data["watched"].get(movie_id) or data["wishlist"].get(movie_id) or call.data.get("movie")
            if not target: return
            
            if "watched_episodes" not in target: target["watched_episodes"] = {}
            for ep_id in episodes:
                target["watched_episodes"][ep_id] = target["watched_episodes"].get(ep_id, {})
                target["watched_episodes"][ep_id]["watched"] = True
            
            # Also store season rating if provided
            if movie_id not in data["watched"]:
                data["watched"][movie_id] = target
                data["wishlist"].pop(movie_id, None)

        elif action == "rate":
            rating = call.data.get("rating")
            if movie_id in data["watched"]:
                data["watched"][movie_id]["user_rating"] = rating
            elif movie_id in data["wishlist"]:
                 data["wishlist"][movie_id]["user_rating"] = rating
        
        elif action == "update_settings":
            data["settings"].update(call.data.get("settings", {}))
        
        await _save()

    hass.services.async_register(DOMAIN, "movie_action", handle_movie_action)

    # --- Register Panel ---
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

    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload a config entry."""
    hass.services.async_remove(DOMAIN, "movie_action")
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
