import { LitElement, html, css } from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

class MovieTrackerPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      data: { type: Object },
      tab: { type: String },
      search: { type: String },
      searchResults: { type: Array },
      searching: { type: Boolean },
      selectedMovie: { type: Object },
      loadingDetail: { type: Boolean },
      toast: { type: String },
      filterGenre: { type: String },
      filterType: { type: String },
      sortBy: { type: String },
      selectedSeason: { type: Number },
      discoverResults: { type: Array },
      discoverLoading: { type: Boolean },
      discoverFilters: { type: Object }
    };
  }

  constructor() {
    super();
    this.data = { watched: {}, wishlist: {}, recommendations: [] };
    this.tab = "dashboard";
    this.search = "";
    this.searchResults = [];
    this.searching = false;
    this.selectedMovie = null;
    this.loadingDetail = false;
    this.toast = "";
    this.filterGenre = "";
    this.filterType = "";
    this.sortBy = "date";
    this.selectedSeason = 0;
    this.discoverResults = [];
    this.discoverLoading = false;
    this.discoverFilters = { type: 'movie', genre: '', year: '', rating: 0 };
    this._dismissedIds = new Set();
  }

  connectedCallback() {
    super.connectedCallback();
    this._fetch();
    // Listen for updates from other instances
    window.addEventListener("movie_tracker_updated", () => this._fetch());
  }

  async _fetch() {
    if (!this.hass) return;
    try {
      const r = await this.hass.fetchWithAuth("/api/movie_tracker/data");
      if (r.ok) {
        this.data = await r.json();
      }
    } catch (e) {
      console.error("Failed to fetch movie data", e);
    }
  }

  async _fetchDiscover() {
    this.discoverLoading = true;
    try {
      const { type, genre, year, rating } = this.discoverFilters;
      let url = `/api/movie_tracker/discover?type=${type}&rating=${rating}`;
      if (genre) url += `&genre=${genre}`;
      if (year) url += `&year=${year}`;
      
      const response = await this.hass.fetchWithAuth(url);
      this.discoverResults = await response.json();
    } catch (e) {
      this._t("Chyba při objevování");
    } finally {
      this.discoverLoading = false;
    }
  }

  _t(m) {
    this.toast = m;
    if (this._toastTimeout) clearTimeout(this._toastTimeout);
    this._toastTimeout = setTimeout(() => { this.toast = "" }, 3000);
  }

  _svc(s, d) {
    return this.hass.callService("movie_tracker", s, d);
  }

  async _doSearch() {
    if (!this.search.trim()) return;
    this.searching = true;
    this.searchResults = [];
    try {
      const r = await this.hass.fetchWithAuth(`/api/movie_tracker/search?q=${encodeURIComponent(this.search)}`);
      if (r.ok) {
        this.searchResults = await r.json();
        if (this.searchResults.length === 0) {
          this._t("Žádné výsledky nenalezeny");
        }
      }
    } catch (e) {
      this._t("Chyba při vyhledávání");
    } finally {
      this.searching = false;
    }
  }

  async _viewDetail(movie) {
    this.loadingDetail = true;
    this.selectedSeason = 0;
    // Set initial data from search results to avoid blank screen/missing poster
    this.selectedMovie = { ...movie };
    
    try {
      const id = movie.id || movie.csfd_id || "";
      const title = movie.title || "";
      const r = await this.hass.fetchWithAuth(`/api/movie_tracker/detail?id=${id}&title=${encodeURIComponent(title)}`);
      if (r.ok) {
        const details = await r.json();
        const localData = this.data.watched[id] || this.data.wishlist[id] || {};
        // Merge order: Search Result < API Details < Local Saved Data
        this.selectedMovie = { ...movie, ...details, ...localData };
      } else {
        this._t("Nepodařilo se načíst detaily");
      }
    } catch (e) {
      this._t("Chyba načítání detailů");
    } finally {
      this.loadingDetail = false;
    }
  }

      if (action === 'not_interested') {
        this._dismissedIds.add(movie.id);
        this.requestUpdate();
      }

      await this._svc("movie_action", { action, movie, ...extra });
      
      const messages = {
        'watch': "Přidáno do shlédnutých",
        'wishlist': "Přidáno do wishlistu",
        'delete_watched': "Odstraněno z knihovny",
        'delete_wishlist': "Odstraněno z wishlistu",
        'update_settings': "Nastavení uloženo"
      };
      
      this._t(messages[action] || "Akce provedena");
      
      if (['watch', 'wishlist'].includes(action)) {
        this.selectedMovie = null;
      }
      
      // Immediate fetch to update UI
      await this._fetch();
    } catch (e) {
      this._t("Akce se nezdařila");
    }
  }

  static get styles() {
    return css`
      :host {
        --primary: #8b5cf6;
        --primary-hover: #7c3aed;
        --secondary: #10b981;
        --danger: #ef4444;
        --bg-dark: #0f172a;
        --card-bg: rgba(30, 41, 59, 0.7);
        --border-color: rgba(255, 255, 255, 0.1);
        --text-main: #f8fafc;
        --text-dim: #94a3b8;
        
        display: block;
        min-height: 100vh;
        background: radial-gradient(circle at top right, #1e1b4b, #0f172a);
        color: var(--text-main);
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
        padding-bottom: 50px;
      }

      .container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 24px;
      }

      .episode-item {
        background: rgba(255,255,255,0.03);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        transition: all 0.3s ease;
      }
      .episode-item.watched {
        background: rgba(139, 92, 246, 0.08);
        border-color: var(--primary);
      }
      .episode-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
      }

      header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 32px;
      }

      .logo {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 24px;
        font-weight: 800;
        letter-spacing: -0.5px;
        background: linear-gradient(to right, #fff, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }

      .logo ha-icon {
        color: var(--primary);
        --mdc-icon-size: 32px;
      }

      /* Search Bar */
      .search-box {
        position: relative;
        background: var(--card-bg);
        backdrop-filter: blur(12px);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 8px 16px;
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 32px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
      }

      .search-box:focus-within {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.3);
      }

      .search-box input {
        flex: 1;
        background: transparent;
        border: none;
        color: white;
        font-size: 16px;
        padding: 10px 0;
        outline: none;
      }

      .search-box button {
        background: var(--primary);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 8px 20px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.2s;
      }

      .search-box button:hover {
        background: var(--primary-hover);
      }

      /* Tabs */
      .tabs {
        display: flex;
        gap: 8px;
        margin-bottom: 24px;
        padding: 4px;
        background: rgba(0,0,0,0.2);
        border-radius: 12px;
        width: fit-content;
      }

      .tab {
        padding: 8px 20px;
        border-radius: 10px;
        cursor: pointer;
        font-weight: 600;
        color: var(--text-dim);
        transition: 0.3s;
      }

      .tab.active {
        background: var(--card-bg);
        color: white;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      }

      /* Toolbar */
      .toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
        flex-wrap: wrap;
        gap: 16px;
      }

      .filter-group {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }

      select {
        background: var(--card-bg);
        color: white;
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 8px 12px;
        font-family: inherit;
        outline: none;
        cursor: pointer;
        transition: border 0.2s;
      }

      select:focus {
        border-color: var(--primary);
      }

      /* Grid */
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 24px;
      }

      .movie-card {
        background: var(--card-bg);
        backdrop-filter: blur(8px);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        cursor: pointer;
        display: flex;
        flex-direction: column;
        position: relative;
      }

      .movie-card:hover {
        transform: translateY(-8px) scale(1.02);
        border-color: rgba(255,255,255,0.2);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
      }

      .poster-wrapper {
        position: relative;
        aspect-ratio: 2/3;
        overflow: hidden;
        background: #1e293b;
      }

      .poster-wrapper img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }

      .rating-badge {
        position: absolute;
        top: 10px;
        right: 10px;
        background: rgba(0,0,0,0.7);
        backdrop-filter: blur(4px);
        padding: 4px 8px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 700;
        border: 1px solid rgba(255,255,255,0.1);
      }

      .btn-dismiss {
        position: absolute;
        top: 8px;
        right: 8px;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: rgba(0,0,0,0.6);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.2s;
        z-index: 10;
        border: 1px solid rgba(255,255,255,0.1);
        backdrop-filter: blur(4px);
        opacity: 0;
      }
      .movie-card:hover .btn-dismiss {
        opacity: 1;
      }
      .btn-dismiss:hover {
        background: var(--danger);
        transform: scale(1.1);
      }

      .rating-high { color: #4ade80; }
      .rating-mid { color: #facc15; }
      .rating-low { color: #f87171; }

      .movie-info {
        padding: 16px;
        flex-grow: 1;
        display: flex;
        flex-direction: column;
      }

      .movie-title {
        font-size: 15px;
        font-weight: 700;
        margin: 0 0 4px 0;
        line-height: 1.3;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }

      .movie-meta {
        font-size: 12px;
        color: var(--text-dim);
      }

      /* Modal */
      .modal-overlay {
        position: fixed;
        inset: 0;
        background: rgba(15, 23, 42, 0.9);
        backdrop-filter: blur(10px);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        padding: 20px;
        animation: fadeIn 0.3s ease;
      }

      .modal-content {
        background: var(--bg-color);
        width: 95%;
        max-width: 1100px;
        height: 80vh;
        border-radius: 32px;
        display: grid;
        grid-template-columns: 400px 1fr;
        overflow: hidden;
        position: relative;
        box-shadow: 0 30px 60px -12px rgba(0,0,0,0.6);
        border: 1px solid var(--border-color);
      }

      @media (max-width: 900px) {
        .modal-content {
          grid-template-columns: 1fr;
          height: 90vh;
          overflow-y: auto;
        }
        .modal-poster {
          height: 350px;
          width: 100%;
        }
      }

      .modal-poster {
        width: 100%;
        height: 100%;
        object-fit: cover;
        background: #05080d;
        border-right: 1px solid var(--border-color);
      }

      .modal-details {
        padding: 40px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 24px;
        background: linear-gradient(135deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0) 100%);
        height: 100%;
        box-sizing: border-box;
      }

      /* Custom scrollbar for premium look */
      .modal-details::-webkit-scrollbar {
        width: 6px;
      }
      .modal-details::-webkit-scrollbar-track {
        background: transparent;
      }
      .modal-details::-webkit-scrollbar-thumb {
        background: rgba(255,255,255,0.1);
        border-radius: 10px;
      }
      .modal-details::-webkit-scrollbar-thumb:hover {
        background: rgba(255,255,255,0.2);
      }

      .modal-details h2 {
        font-size: 32px;
        margin: 0 0 8px 0;
        font-weight: 800;
      }

      .genres {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 24px;
      }

      .genre-tag {
        padding: 4px 12px;
        background: rgba(139, 92, 246, 0.15);
        color: #c4b5fd;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
      }

      @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }
      .spin {
        animation: spin 1s linear infinite;
        display: inline-block;
      }

      .plot {
        line-height: 1.6;
        color: var(--text-dim);
        margin-bottom: 32px;
      }

      .actions {
        display: flex;
        flex-direction: column;
        gap: 16px;
        margin-top: auto;
      }
      .actions-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }
      .rating-box {
        background: rgba(255,255,255,0.03);
        border: 1px solid var(--border-color);
        border-radius: 20px;
        padding: 20px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
      }

      .btn {
        padding: 12px 24px;
        border-radius: 12px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.2s;
        border: none;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        font-size: 14px;
        background: rgba(255,255,255,0.05);
        color: white;
      }
      .btn:hover {
        background: rgba(255,255,255,0.1);
      }
      .btn-primary {
        background: var(--primary);
        color: white;
      }
      .btn-secondary {
        background: rgba(255,255,255,0.08);
        color: white;
      }
      
      .btn-hero {
        background: var(--primary-gradient);
        color: white;
        border: none;
        padding: 20px;
        border-radius: 20px;
        font-size: 18px;
        font-weight: 800;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        cursor: pointer;
        transition: all 0.3s;
        text-decoration: none;
        box-shadow: 0 10px 20px -5px rgba(139, 92, 246, 0.4);
        margin-bottom: 8px;
        width: 100%;
        box-sizing: border-box;
      }
      .btn-hero:hover {
        transform: translateY(-2px);
        box-shadow: 0 15px 30px -5px rgba(139, 92, 246, 0.6);
        filter: brightness(1.1);
      }
        gap: 8px;
      }

      .btn-primary { background: var(--primary); color: white; }
      .btn-secondary { background: rgba(255,255,255,0.1); color: white; }
      .btn-secondary:hover { background: rgba(255,255,255,0.2); }
      
      .toast {
        position: fixed;
        bottom: 32px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--primary);
        color: white;
        padding: 12px 32px;
        border-radius: 50px;
        font-weight: 600;
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        z-index: 2000;
        animation: slideUp 0.3s ease;
      }

      @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
      @keyframes slideUp { from { transform: translate(-50%, 20px); opacity: 0; } to { transform: translate(-50%, 0); opacity: 1; } }

      /* Empty states */
      .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: var(--text-dim);
      }

      .empty-state ha-icon {
        --mdc-icon-size: 64px;
        margin-bottom: 16px;
        opacity: 0.5;
      }
    `;
  }

  render() {
    const watched = Object.values(this.data.watched || {});
    const wishlist = Object.values(this.data.wishlist || {});

    return html`
      <div class="container">
        <header>
          <div class="logo">
            <ha-icon icon="mdi:movie-roll"></ha-icon>
            Filmotéka
          </div>
          <div class="settings-nav">
             <ha-icon 
                icon="mdi:refresh" 
                style="cursor:pointer; opacity:0.7" 
                @click=${this._fetch}
             ></ha-icon>
          </div>
        </header>

        <div class="search-box">
          <ha-icon icon="mdi:magnify"></ha-icon>
          <input 
            type="text" 
            placeholder="Hledat film nebo seriál..." 
            .value=${this.search}
            @input=${e => this.search = e.target.value}
            @keyup=${e => e.key === 'Enter' && this._doSearch()}
          >
          <button @click=${this._doSearch} ?disabled=${this.searching}>
            ${this.searching ? 'Načítám...' : 'Hledat'}
          </button>
        </div>

        <div class="tabs">
          <div class="tab ${this.tab === 'dashboard' ? 'active' : ''}" @click=${() => this.tab = 'dashboard'}>Přehled</div>
          <div class="tab ${this.tab === 'discover' ? 'active' : ''}" @click=${() => { this.tab = 'discover'; if (this.discoverResults.length === 0) this._fetchDiscover(); }}>Objevovat</div>
          <div class="tab ${this.tab === 'library' ? 'active' : ''}" @click=${() => this.tab = 'library'}>Shlédnuto</div>
          <div class="tab ${this.tab === 'wishlist' ? 'active' : ''}" @click=${() => this.tab = 'wishlist'}>Wishlist</div>
        </div>

        ${this.searchResults.length > 0 ? html`
          <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h3>Výsledky hledání</h3>
            <button class="btn btn-secondary" style="padding: 4px 12px; font-size: 12px;" @click=${() => this.searchResults = []}>Zavřít výsledky</button>
          </div>
          <div class="grid">
            ${this.searchResults.map(m => this._renderMovieCard(m))}
          </div>
          <hr style="margin: 40px 0; opacity: 0.1;">
        ` : ''}

        ${this._renderContent(watched, wishlist)}

        ${this.selectedMovie ? this._renderModal() : ''}
        ${this.toast ? html`<div class="toast">${this.toast}</div>` : ''}
      </div>
    `;
  }

  _renderContent(watched, wishlist) {
    if (this.tab === 'discover') return this._renderDiscover();
    if (this.tab === 'dashboard') return this._renderHome();
    return this._renderList(watched, wishlist);
  }

  _renderHome() {
    const watchedList = Object.values(this.data.watched || {});
    return html`
      <section>
        <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
          <h3 style="margin:0">✨ Doporučeno pro vás</h3>
          <button class="btn btn-secondary" style="padding: 4px 12px; font-size: 12px; display:flex; align-items:center; gap:4px" 
                  @click=${this._fetch} ?disabled=${this.loadingDetail}>
            <ha-icon icon="mdi:refresh" class="${this.loadingDetail ? 'spin' : ''}"></ha-icon> Obnovit tipy
          </button>
        </div>
        
        <div class="grid" style="margin-bottom: 48px;">
          ${(() => {
            const serverDismissed = Object.keys(this.data.not_interested || {});
            const filtered = (this.data.recommendations || []).filter(m => 
              !this._dismissedIds.has(m.id) && !serverDismissed.includes(m.id)
            );
            if (!filtered.length) return html`<div class="empty-state" style="grid-column: 1/-1"><p>Žádná doporučení. Zkuste něco přidat do Shlédnuto!</p></div>`;
            return filtered.map(m => this._renderMovieCard(m, true));
          })()}
        </div>
        
        <h3 style="margin-bottom: 20px;">🍿 Shlédnuto</h3>
        ${watchedList.length === 0 ? html`
          <div class="empty-state">
            <ha-icon icon="mdi:movie-open-play"></ha-icon>
            <p>Zatím jste nic nesledovali. Zkuste něco najít!</p>
          </div>
        ` : html`
          <div class="grid">
            ${watchedList.slice(-6).reverse().map(m => this._renderMovieCard(m))}
          </div>
        `}
      </section>
    `;
  }

  _renderList(watched, wishlist) {
    const list = this.tab === 'library' ? watched : wishlist;
    
    // Filtering and Sorting
    let filtered = [...list];
    if (this.filterGenre) {
      filtered = filtered.filter(m => m.genres?.includes(this.filterGenre));
    }
    if (this.filterType) {
      filtered = filtered.filter(m => m.type === this.filterType);
    }

    const sorted = filtered.sort((a, b) => {
      if (this.sortBy === 'rating') return (parseInt(b.rating) || 0) - (parseInt(a.rating) || 0);
      if (this.sortBy === 'user_rating') return (b.user_rating || 0) - (a.user_rating || 0);
      if (this.sortBy === 'year') return (parseInt(b.year) || 0) - (parseInt(a.year) || 0);
      // Default: date (newest first)
      const dateA = a.watched_at || a.added_at || '';
      const dateB = b.watched_at || b.added_at || '';
      return dateB.localeCompare(dateA);
    });

    const allGenres = [...new Set(list.flatMap(m => m.genres || []))].sort();

    return html`
      <section>
        <div class="toolbar">
          <div class="filter-group">
            <select @change=${e => { this.sortBy = e.target.value; this.requestUpdate(); }}>
              <option value="date">Nejnovější</option>
              <option value="rating">Dle ČSFD</option>
              <option value="user_rating">Moje hodnocení</option>
              <option value="year">Rok vydání</option>
            </select>
            <select @change=${e => { this.filterGenre = e.target.value; this.requestUpdate(); }}>
              <option value="">Všechny žánry</option>
              ${allGenres.map(g => html`<option value="${g}" ?selected=${this.filterGenre === g}>${g}</option>`)}
            </select>
            <select @change=${e => { this.filterType = e.target.value; this.requestUpdate(); }}>
              <option value="">Vše (Film/Seriál)</option>
              <option value="movie">Jen filmy</option>
              <option value="series">Jen seriály</option>
            </select>
          </div>
          <div style="font-size: 13px; color: var(--text-dim)">
            Nalezeno: ${sorted.length}
          </div>
        </div>

        ${sorted.length === 0 ? html`
          <div class="empty-state">
            <ha-icon icon="mdi:layers-off"></ha-icon>
            <p>Seznam je zatím prázdný nebo žádný film neodpovídá filtru.</p>
          </div>
        ` : html`
          <div class="grid">
            ${sorted.map(m => this._renderMovieCard(m))}
          </div>
        `}
      </section>
    `;
  }

  _renderMovieCard(m, isRecommendation = false) {
    const ratingVal = parseInt(m.rating) || 0;
    const ratingClass = ratingVal >= 75 ? 'rating-high' : (ratingVal >= 50 ? 'rating-mid' : 'rating-low');
    
    return html`
      <div class="movie-card" @click=${() => this._viewDetail(m)}>
        <div class="poster-wrapper">
          <img src="${m.poster || 'https://dummyimage.com/300x450/1e293b/f8fafc&text=Bez+plakátu'}" loading="lazy">
          ${m.rating ? html`<div class="rating-badge ${ratingClass}">${m.rating}</div>` : ''}
          ${isRecommendation ? html`
            <div class="btn-dismiss" title="Nezajímá mě" @click=${(e) => { e.stopPropagation(); this._action('not_interested', m); }}>
              <ha-icon icon="mdi:close" style="--mdc-icon-size: 18px;"></ha-icon>
            </div>
          ` : ''}
          ${m.user_rating ? html`<div class="rating-badge" style="top: auto; bottom: 8px; background: var(--primary); font-size: 10px;">${'⭐'.repeat(m.user_rating)}</div>` : ''}
        </div>
        <div class="movie-info">
          <h4 class="movie-title">${m.title}</h4>
          <div class="movie-meta">${m.year} • ${m.type === 'series' ? 'Seriál' : 'Film'}</div>
        </div>
      </div>
    `;
  }

  _renderModal() {
    const m = this.selectedMovie;
    const isWatched = !!this.data.watched[m.id];
    const isWishlist = !!this.data.wishlist[m.id];

    return html`
      <div class="modal-overlay" @click=${() => this.selectedMovie = null}>
        <div class="modal-content" @click=${e => e.stopPropagation()}>
          <img class="modal-poster" 
               src="${m.poster || 'https://dummyimage.com/300x450/1e293b/f8fafc&text=Bez+plakátu'}"
               @error=${e => e.target.src = 'https://dummyimage.com/300x450/1e293b/f8fafc&text=Plakát+nenalezen'}>
          <div class="modal-details">
            <div style="display:flex; justify-content: space-between; align-items: flex-start;">
              <h2>${m.title}</h2>
              <button style="background:none; border:none; color:white; cursor:pointer" @click=${() => this.selectedMovie = null}>
                <ha-icon icon="mdi:close"></ha-icon>
              </button>
            </div>
            
            <div style="color:var(--text-dim); margin-bottom: 16px;">${m.origin}</div>
            
            <div class="genres">
              ${m.genres?.map(g => html`<span class="genre-tag">${g}</span>`)}
              ${m.rating ? html`<span class="genre-tag" style="background:rgba(255,255,255,0.1); color:white">⭐ ${m.rating}</span>` : ''}
            </div>

            <p class="plot">${m.description || 'K tomuto titulu zatím není k dispozici žádný popis.'}</p>

            ${m.seasons?.length ? html`
              <div class="seasons-container" style="margin-top: 32px; border-top: 1px solid var(--border-color); padding-top: 24px;">
                <h3 style="margin-bottom: 16px;">Sezóny a epizody</h3>
                <div style="display:flex; gap: 8px; overflow-x: auto; padding-bottom: 12px; margin-bottom: 16px;">
                  ${m.seasons.map((s, idx) => html`
                    <button 
                      class="btn ${this.selectedSeason === idx ? 'btn-primary' : 'btn-secondary'}"
                      style="white-space: nowrap; padding: 6px 16px; font-size: 13px;"
                      @click=${() => { this.selectedSeason = idx; this.requestUpdate(); }}
                    >${s.name}</button>
                  `)}
                </div>
                
                <div style="display:flex; justify-content: flex-end; margin-bottom: 16px;">
                  <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 12px;" @click=${() => {
                    const s = m.seasons[this.selectedSeason];
                    this._action('watch_season', m, { 
                      season_num: this.selectedSeason + 1, 
                      episodes: s.episodes.map(e => e.id) 
                    });
                  }}>
                    <ha-icon icon="mdi:check-all" style="--mdc-icon-size: 16px; margin-right: 4px;"></ha-icon> Označit celou řadu jako shlédnutou
                  </button>
                </div>
                
                <div class="episodes-list" style="display: flex; flex-direction: column; gap: 8px;">
                  ${m.seasons[this.selectedSeason || 0]?.episodes.map(ep => {
                    const epData = (this.data.watched[m.id] || this.data.wishlist[m.id])?.watched_episodes?.[ep.id] || {};
                    const isEpWatched = epData.watched;
                    const epRating = epData.rating || 0;
                    
                    return html`
                    <div class="episode-item ${isEpWatched ? 'watched' : ''}">
                      <div class="episode-header">
                        <div style="flex: 1">
                          <div style="font-weight: 700; font-size: 14px; display:flex; align-items:center; gap:8px">
                            ${isEpWatched ? html`<ha-icon icon="mdi:check-circle" style="color:var(--primary); --mdc-icon-size: 18px;"></ha-icon>` : ''}
                            ${ep.number ? `${ep.number}. ` : ''}${ep.title}
                          </div>
                          ${ep.overview ? html`<div style="font-size: 12px; color: var(--text-dim); margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${ep.overview}</div>` : ''}
                        </div>
                        <div style="display:flex; gap:8px">
                           <a href="${ep.url}" target="_blank" class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;">
                            <ha-icon icon="mdi:play" style="--mdc-icon-size: 18px;"></ha-icon>
                          </a>
                           <button class="btn ${isEpWatched ? 'btn-primary' : 'btn-secondary'}" style="padding: 6px 12px; font-size: 12px;" @click=${() => this._action('watch_episode', m, { episode_id: ep.id })}>
                            <ha-icon icon="${isEpWatched ? 'mdi:eye-off' : 'mdi:eye'}" style="--mdc-icon-size: 18px;"></ha-icon>
                          </button>
                        </div>
                      </div>
                      
                      <div style="display:flex; align-items:center; gap:12px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.05)">
                        <span style="font-size: 10px; font-weight:700; color:var(--text-dim)">HODNOCENÍ DÍLU:</span>
                        <div style="display:flex; gap:2px">
                          ${[1,2,3,4,5].map(star => html`
                            <ha-icon 
                              icon="${epRating >= star ? 'mdi:star' : 'mdi:star-outline'}" 
                              style="cursor:pointer; color: ${epRating >= star ? 'var(--primary)' : 'var(--text-dim)'}; --mdc-icon-size: 18px;"
                              @click=${() => this._action('rate_episode', m, { episode_id: ep.id, rating: star })}
                            ></ha-icon>
                          `)}
                        </div>
                      </div>
                    </div>
                  `})}
                </div>
              </div>
            ` : ''}

            <div class="actions">
              <a href="${m.hellspy_url}" target="_blank" class="btn-hero">
                <ha-icon icon="mdi:play" style="--mdc-icon-size: 28px;"></ha-icon> Sledovat
              </a>
              
              <div class="rating-box">
                <div style="display:flex; justify-content: space-between; width: 100%; align-items: center;">
                  <span style="font-weight: 700; color: var(--text-dim); font-size: 13px;">Vaše hodnocení</span>
                  <span style="color:var(--primary); font-weight: 800; font-size: 13px;">${m.user_rating ? '⭐'.repeat(m.user_rating) : 'Zatím nehodnoceno'}</span>
                </div>
                <div style="display:flex; justify-content: center; gap: 8px;">
                  ${[1,2,3,4,5].map(num => html`
                    <ha-icon 
                      icon="${m.user_rating >= num ? 'mdi:star' : 'mdi:star-outline'}"
                      style="cursor:pointer; color: ${m.user_rating >= num ? 'var(--primary)' : 'var(--text-dim)'}; --mdc-icon-size: 32px; transition: transform 0.2s"
                      @click=${() => this._action('rate', m, { rating: num })}
                    ></ha-icon>
                  `)}
                </div>
              </div>

              <div class="actions-row">
                ${!isWatched ? html`
                  <button class="btn btn-secondary" @click=${() => this._action('watch', m)}>
                    <ha-icon icon="mdi:check"></ha-icon> Shlédnuto
                  </button>
                ` : html`
                   <button class="btn btn-secondary" style="color:var(--danger)" @click=${() => this._action('delete_watched', m)}>
                    <ha-icon icon="mdi:delete"></ha-icon> Odebrat
                  </button>
                `}

                ${!isWatched && !isWishlist ? html`
                  <button class="btn btn-secondary" @click=${() => this._action('wishlist', m)}>
                    <ha-icon icon="mdi:heart-outline"></ha-icon> Wishlist
                  </button>
                ` : (isWishlist ? html`
                   <button class="btn btn-secondary" style="color:var(--danger)" @click=${() => this._action('delete_wishlist', m)}>
                    <ha-icon icon="mdi:delete"></ha-icon> Z wishlistu
                  </button>
                ` : '')}
              </div>
            </div>
              ` : '')}

              <a href="${m.url}" target="_blank" class="btn btn-secondary" style="height: 50px; text-decoration:none; display:flex; align-items:center; justify-content:center">
                <ha-icon icon="mdi:open-in-new"></ha-icon> ČSFD (${m.rating})
              </a>
            </div>
          </div>
        </div>
      </div>
    `;
  }
  _renderDiscover() {
    const genres = [
      {id: 28, name: "Akční"}, {id: 12, name: "Dobrodružný"}, {id: 16, name: "Animovaný"},
      {id: 35, name: "Komedie"}, {id: 80, name: "Krimi"}, {id: 99, name: "Dokumentární"},
      {id: 18, name: "Drama"}, {id: 10751, name: "Rodinný"}, {id: 14, name: "Fantasy"},
      {id: 27, name: "Horor"}, {id: 10749, name: "Romantický"}, {id: 878, name: "Sci-Fi"},
      {id: 53, name: "Thriller"}
    ];
    
    return html`
      <section>
        <div class="toolbar" style="background: rgba(255,255,255,0.03); padding: 20px; border-radius: 16px; margin-bottom: 32px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
          <div class="filter-group" style="display: flex; gap: 12px; flex-wrap: wrap;">
            <select @change=${e => { this.discoverFilters.type = e.target.value; this._fetchDiscover(); }}>
              <option value="movie">Filmy</option>
              <option value="tv">Seriály</option>
            </select>
            <select @change=${e => { this.discoverFilters.genre = e.target.value; this._fetchDiscover(); }}>
              <option value="">Všechny žánry</option>
              ${genres.map(g => html`<option value="${g.id}">${g.name}</option>`)}
            </select>
            <input type="number" placeholder="Rok" style="width: 80px; background: var(--card-bg); color: white; border: 1px solid var(--border-color); border-radius: 10px; padding: 8px 12px;" 
                   @change=${e => { this.discoverFilters.year = e.target.value; this._fetchDiscover(); }}>
            <select @change=${e => { this.discoverFilters.rating = e.target.value; this._fetchDiscover(); }}>
              <option value="0">Jakékoliv hodnocení</option>
              <option value="5">Nad 50%</option>
              <option value="7">Nad 70%</option>
              <option value="8">Nad 80%</option>
            </select>
          </div>
          <button class="btn btn-primary" @click=${this._fetchDiscover} ?disabled=${this.discoverLoading} style="min-width: 100px;">
             ${this.discoverLoading ? html`<ha-circular-progress active size="small"></ha-circular-progress>` : 'Obnovit'}
          </button>
        </div>

        ${this.discoverLoading && this.discoverResults.length === 0 ? html`
          <div style="display:flex; justify-content:center; padding: 100px;">
            <ha-circular-progress active></ha-circular-progress>
          </div>
        ` : html`
          <div class="grid">
            ${this.discoverResults.map(m => this._renderMovieCard(m))}
          </div>
        `}
      </section>
    `;
  }
}

customElements.define("movie-tracker-panel", MovieTrackerPanel);
