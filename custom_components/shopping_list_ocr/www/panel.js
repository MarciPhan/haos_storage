import {
    LitElement,
    html,
    css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

/* ── Load barcode scanner lib lazily ────────────────────────────────── */
let scannerReady = false;
const scannerScript = document.createElement("script");
scannerScript.src = "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js";
scannerScript.onload = () => { scannerReady = true; };
document.head.appendChild(scannerScript);

/* ── Main Panel ─────────────────────────────────────────────────────── */
class ShoppingListPanel extends LitElement {

    static get properties() {
        return {
            hass:        { type: Object },
            data:        { type: Object },
            activeTab:   { type: String },
            showScanner: { type: Boolean },
            uploading:   { type: Boolean },
            toastMsg:    { type: String },
        };
    }

    constructor() {
        super();
        this.data = { inventory: {}, pending_receipts: {}, recipes: {}, keep_config: {} };
        this.activeTab  = "inventory";
        this.showScanner = false;
        this.uploading   = false;
        this.toastMsg    = "";
        this._scanner    = null;
    }

    connectedCallback() {
        super.connectedCallback();
        this._fetchData();
        this._unsub = null;
        if (this.hass?.connection) {
            this._unsub = this.hass.connection.subscribeEvents(
                () => this._fetchData(), "shopping_list_ocr_updated"
            );
        }
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        if (this._unsub) this._unsub.then?.(u => u?.());
    }

    async _fetchData() {
        if (!this.hass) return;
        try {
            const r = await this.hass.fetchWithAuth("/api/shopping_list/data");
            if (r.ok) this.data = await r.json();
        } catch (e) { console.error("Fetch error:", e); }
    }

    _toast(msg) {
        this.toastMsg = msg;
        setTimeout(() => { this.toastMsg = ""; }, 4000);
    }

    /* ── Styles ──────────────────────────────────────────────────────── */
    static get styles() {
        return css`
            :host {
                --clr-accent: #4361ee;
                --clr-success: #06d6a0;
                --clr-danger: #ef476f;
                --clr-warn: #ffd166;
                --radius: 14px;
                display: block;
                min-height: 100vh;
                background: var(--primary-background-color, #0d1117);
                color: var(--primary-text-color, #c9d1d9);
                font-family: 'Segoe UI', Roboto, sans-serif;
            }

            /* Layout */
            .page { padding: 24px; max-width: 1280px; margin: 0 auto; }

            /* Header */
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; gap: 16px; flex-wrap: wrap; }
            .header h1 { font-weight: 600; font-size: 2rem; margin: 0; display: flex; align-items: center; gap: 10px; letter-spacing: -0.5px; }
            .header-actions { display: flex; gap: 10px; flex-wrap: wrap; }

            /* Tabs */
            .tabs { display: flex; gap: 4px; margin-bottom: 28px; background: var(--card-background-color, #161b22); border-radius: var(--radius); padding: 4px; width: fit-content; }
            .tab { padding: 10px 20px; cursor: pointer; border-radius: 10px; font-weight: 600; font-size: 0.9rem; transition: all 0.2s; user-select: none; color: var(--secondary-text-color, #8b949e); }
            .tab:hover { background: rgba(255,255,255,0.05); }
            .tab.active { background: var(--clr-accent); color: #fff; box-shadow: 0 2px 12px rgba(67,97,238,0.35); }
            .tab .badge { background: var(--clr-danger); color: #fff; font-size: 0.7rem; padding: 2px 7px; border-radius: 20px; margin-left: 6px; }

            /* Grid */
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px; }

            /* Cards */
            .card { background: var(--card-background-color, #161b22); border-radius: var(--radius); overflow: hidden; transition: transform 0.2s, box-shadow 0.2s; border: 1px solid rgba(255,255,255,0.06); }
            .card:hover { transform: translateY(-3px); box-shadow: 0 8px 30px rgba(0,0,0,0.3); }
            .card-body { padding: 18px; display: flex; flex-direction: column; gap: 8px; }
            .card-img { width: 100%; height: 150px; object-fit: cover; background: #21262d; }
            .card-title { font-weight: 600; font-size: 1.05rem; margin: 0; }
            .card-meta { font-size: 0.8rem; color: var(--secondary-text-color, #8b949e); }
            .card-value { font-size: 1.6rem; font-weight: 700; }
            .card-value small { font-size: 0.85rem; font-weight: 400; opacity: 0.7; }

            /* Store badge */
            .store { position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.7); backdrop-filter: blur(4px); color: #fff; padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }

            /* Buttons */
            .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 10px 20px; border: none; border-radius: 10px; font-weight: 600; font-size: 0.88rem; cursor: pointer; transition: all 0.15s; text-decoration: none; white-space: nowrap; }
            .btn-primary { background: var(--clr-accent); color: #fff; }
            .btn-primary:hover { filter: brightness(1.15); }
            .btn-success { background: var(--clr-success); color: #0d1117; }
            .btn-success:hover { filter: brightness(1.1); }
            .btn-ghost { background: transparent; border: 1px solid rgba(255,255,255,0.15); color: var(--primary-text-color, #c9d1d9); }
            .btn-ghost:hover { background: rgba(255,255,255,0.06); }
            .btn-sm { padding: 6px 14px; font-size: 0.82rem; }
            .btn-block { width: 100%; }

            /* Toolbar */
            .toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 24px; flex-wrap: wrap; background: var(--card-background-color, #161b22); padding: 14px 20px; border-radius: var(--radius); border: 1px solid rgba(255,255,255,0.06); }
            .toolbar input[type="text"] { flex: 1; min-width: 180px; padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04); color: inherit; font-size: 0.9rem; outline: none; }
            .toolbar input[type="text"]:focus { border-color: var(--clr-accent); box-shadow: 0 0 0 3px rgba(67,97,238,0.2); }

            /* Qty row */
            .qty-row { display: flex; gap: 6px; margin-top: auto; }
            .qty-btn { flex: 1; padding: 8px; border: 1px solid rgba(255,255,255,0.1); background: transparent; color: inherit; border-radius: 8px; font-weight: 700; font-size: 1rem; cursor: pointer; transition: background 0.15s; }
            .qty-btn:hover { background: rgba(255,255,255,0.08); }

            /* Receipt item row */
            .receipt-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem; }
            .receipt-price { font-weight: 600; white-space: nowrap; }

            /* Empty state */
            .empty { text-align: center; padding: 60px 20px; color: var(--secondary-text-color, #8b949e); }
            .empty ha-icon { --mdi-icon-size: 48px; margin-bottom: 16px; opacity: 0.3; }
            .empty p { margin: 8px 0 0; font-size: 0.95rem; }

            /* Modal */
            .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.9); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 10000; padding: 24px; }
            #reader { width: 100%; max-width: 480px; border-radius: var(--radius); overflow: hidden; }

            /* Toast */
            .toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); background: var(--card-background-color, #161b22); color: var(--primary-text-color); padding: 12px 28px; border-radius: 12px; font-size: 0.9rem; box-shadow: 0 8px 30px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); z-index: 10001; animation: fadeIn 0.3s; }
            @keyframes fadeIn { from { opacity: 0; transform: translateX(-50%) translateY(20px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }

            /* Config form */
            .config-card { max-width: 480px; margin: 0 auto; background: var(--card-background-color, #161b22); padding: 32px; border-radius: var(--radius); border: 1px solid rgba(255,255,255,0.06); display: flex; flex-direction: column; gap: 16px; }
            .config-card input { padding: 12px 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04); color: inherit; font-size: 0.9rem; width: 100%; box-sizing: border-box; }
        `;
    }

    /* ── Render ───────────────────────────────────────────────────────── */
    render() {
        const pCount = Object.keys(this.data.pending_receipts || {}).length;
        return html`
        <div class="page">
            <div class="header">
                <h1><ha-icon icon="mdi:cart-outline"></ha-icon> Nákupník</h1>
                <div class="header-actions">
                    <button class="btn btn-primary" @click=${this._toggleScanner}>
                        <ha-icon icon="mdi:barcode-scan"></ha-icon> Skenovat EAN
                    </button>
                </div>
            </div>

            <div class="tabs">
                <div class="tab ${this.activeTab === 'inventory' ? 'active' : ''}" @click=${() => this.activeTab = 'inventory'}>
                    <ha-icon icon="mdi:warehouse"></ha-icon> Sklad
                </div>
                <div class="tab ${this.activeTab === 'receipts' ? 'active' : ''}" @click=${() => this.activeTab = 'receipts'}>
                    <ha-icon icon="mdi:receipt-text-outline"></ha-icon> Účtenky
                    ${pCount > 0 ? html`<span class="badge">${pCount}</span>` : ""}
                </div>
                <div class="tab ${this.activeTab === 'recipes' ? 'active' : ''}" @click=${() => this.activeTab = 'recipes'}>
                    <ha-icon icon="mdi:chef-hat"></ha-icon> Recepty
                </div>
                <div class="tab ${this.activeTab === 'sync' ? 'active' : ''}" @click=${() => this.activeTab = 'sync'}>
                    <ha-icon icon="mdi:sync"></ha-icon> Keep
                </div>
            </div>

            ${this.activeTab === 'inventory' ? this._renderInventory() : ''}
            ${this.activeTab === 'receipts'  ? this._renderReceipts()  : ''}
            ${this.activeTab === 'recipes'   ? this._renderRecipes()   : ''}
            ${this.activeTab === 'sync'      ? this._renderSync()      : ''}

            ${this.showScanner ? this._renderScannerModal() : ''}
            ${this.toastMsg ? html`<div class="toast">${this.toastMsg}</div>` : ''}
        </div>`;
    }

    /* ── Inventory Tab ───────────────────────────────────────────────── */
    _renderInventory() {
        const items = Object.values(this.data.inventory || {});
        return html`
        <section>
            <div class="toolbar">
                <input id="ean-input" type="text" placeholder="EAN kód…" @keyup=${e => { if (e.key === 'Enter') this._addByEan(); }}>
                <button class="btn btn-primary" @click=${this._addByEan}>Přidat</button>
            </div>
            ${items.length === 0 ? html`
                <div class="empty">
                    <ha-icon icon="mdi:package-variant"></ha-icon>
                    <p><strong>Sklad je prázdný</strong></p>
                    <p>Naskenujte EAN kód nebo nahrajte účtenku.</p>
                </div>
            ` : html`
                <div class="grid">
                    ${items.map(item => html`
                        <div class="card" style="position:relative">
                            ${item.image_url ? html`<img class="card-img" src="${item.image_url}" loading="lazy" onerror="this.style.display='none'">` : ''}
                            ${item.store ? html`<span class="store">${item.store}</span>` : ''}
                            <div class="card-body">
                                <h3 class="card-title">${item.name}</h3>
                                <div class="card-value">${item.quantity} <small>${item.unit || 'ks'}</small></div>
                                ${item.last_price ? html`<div class="card-meta">${item.last_price} Kč</div>` : ''}
                                <div class="qty-row">
                                    <button class="qty-btn" @click=${() => this._updateQty(item.name, -1)}>−</button>
                                    <button class="qty-btn" @click=${() => this._updateQty(item.name, 1)}>+</button>
                                </div>
                            </div>
                        </div>
                    `)}
                </div>
            `}
        </section>`;
    }

    /* ── Receipts Tab ────────────────────────────────────────────────── */
    _renderReceipts() {
        const receipts = Object.values(this.data.pending_receipts || {});
        return html`
        <section>
            <div class="toolbar">
                <input type="file" id="receipt-file" accept="image/*" capture="environment"
                    style="display:none" @change=${this._handleUpload}>
                <button class="btn btn-success" @click=${() => this.shadowRoot.getElementById('receipt-file').click()}
                    ?disabled=${this.uploading}>
                    <ha-icon icon="mdi:camera"></ha-icon>
                    ${this.uploading ? 'Nahrávám…' : 'Nahrát účtenku'}
                </button>
                <button class="btn btn-ghost" @click=${this._scanFolder}>
                    <ha-icon icon="mdi:folder-search-outline"></ha-icon> Skenovat složku
                </button>
            </div>
            ${receipts.length === 0 ? html`
                <div class="empty">
                    <ha-icon icon="mdi:receipt-text-check-outline"></ha-icon>
                    <p><strong>Žádné účtenky ke zpracování</strong></p>
                    <p>Nahrajte fotku účtenky nebo skenujte složku.</p>
                </div>
            ` : html`
                <div class="grid">
                    ${receipts.map(r => html`
                        <div class="card" style="position:relative">
                            ${r.store ? html`<span class="store">${r.store}</span>` : ''}
                            <div class="card-body">
                                <div class="card-meta">${new Date(r.date).toLocaleString("cs-CZ")}</div>
                                <div style="margin:8px 0">
                                    ${r.items.map(i => html`
                                        <div class="receipt-item">
                                            <span>${i.name}</span>
                                            <span class="receipt-price">${i.price} Kč</span>
                                        </div>
                                    `)}
                                </div>
                                <div class="card-meta" style="margin-bottom:8px">
                                    Celkem: <strong>${r.items.reduce((s, i) => s + i.price, 0).toFixed(0)} Kč</strong>
                                    · ${r.items.length} položek
                                </div>
                                <button class="btn btn-primary btn-block" @click=${() => this._confirmReceipt(r.id)}>
                                    <ha-icon icon="mdi:check"></ha-icon> Potvrdit do skladu
                                </button>
                            </div>
                        </div>
                    `)}
                </div>
            `}
        </section>`;
    }

    /* ── Recipes Tab ─────────────────────────────────────────────────── */
    _renderRecipes() {
        const recipes = Object.values(this.data.recipes || {});
        return html`
        <section>
            <div class="toolbar">
                <input id="recipe-url" type="text" placeholder="URL receptu (toprecepty.cz, recepty.cz…)"
                    @keyup=${e => { if (e.key === 'Enter') this._addRecipe(); }}>
                <button class="btn btn-primary" @click=${this._addRecipe}>
                    <ha-icon icon="mdi:plus"></ha-icon> Přidat
                </button>
            </div>
            ${recipes.length === 0 ? html`
                <div class="empty">
                    <ha-icon icon="mdi:book-open-variant"></ha-icon>
                    <p><strong>Zatím žádné recepty</strong></p>
                    <p>Vložte URL receptu a systém ho stáhne i s PDF.</p>
                </div>
            ` : html`
                <div class="grid">
                    ${recipes.map(r => html`
                        <div class="card">
                            ${r.image_url ? html`<img class="card-img" src="${r.image_url}" loading="lazy" onerror="this.style.display='none'">` : ''}
                            <div class="card-body">
                                <h3 class="card-title">${r.title}</h3>
                                <div class="card-meta">${r.ingredients?.length || 0} ingrediencí</div>
                                <div style="display:flex; flex-direction:column; gap:8px; margin-top:auto">
                                    <a href="${r.pdf_url}" target="_blank" class="btn btn-ghost btn-block" style="text-decoration:none">
                                        <ha-icon icon="mdi:file-pdf-box"></ha-icon> PDF
                                    </a>
                                    <button class="btn btn-primary btn-block" @click=${() => this._addIngredientsToList(r)}>
                                        <ha-icon icon="mdi:cart-plus"></ha-icon> Do nákupu
                                    </button>
                                </div>
                            </div>
                        </div>
                    `)}
                </div>
            `}
        </section>`;
    }

    /* ── Sync Tab ─────────────────────────────────────────────────────── */
    _renderSync() {
        const c = this.data.keep_config || {};
        return html`
        <section>
            <div class="config-card">
                <h2 style="margin:0;font-size:1.4rem">
                    <ha-icon icon="mdi:google"></ha-icon> Google Keep
                </h2>
                <p class="card-meta" style="margin:0">
                    Synchronizuje váš nákupní seznam z Home Assistanta do Google Keep.
                    Potřebujete <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color:var(--clr-accent)">Heslo aplikace</a>.
                </p>
                <input id="keep-user" type="text" placeholder="Google E-mail" .value="${c.username || ''}">
                <input id="keep-pass" type="password" placeholder="App Password" .value="${c.password || ''}">
                <input id="keep-title" type="text" placeholder="Název poznámky v Keep" .value="${c.title || 'Nákup'}">
                <button class="btn btn-primary btn-block" @click=${this._syncToKeep}>
                    <ha-icon icon="mdi:sync"></ha-icon> Synchronizovat
                </button>
            </div>
        </section>`;
    }

    /* ── Scanner Modal ────────────────────────────────────────────────── */
    _renderScannerModal() {
        return html`
        <div class="modal">
            <div id="reader"></div>
            <button class="btn btn-ghost" style="margin-top:20px;background:rgba(255,255,255,0.1)"
                @click=${this._toggleScanner}>Zavřít skener</button>
        </div>`;
    }

    /* ── Actions ──────────────────────────────────────────────────────── */

    async _handleUpload(e) {
        const file = e.target.files?.[0];
        if (!file) return;
        this.uploading = true;
        const fd = new FormData();
        fd.append("file", file);
        try {
            const r = await this.hass.fetchWithAuth("/api/shopping_list/upload", {
                method: "POST", body: fd,
            });
            if (r.ok) {
                this._toast("Účtenka nahrána, zpracovávám…");
                setTimeout(() => this._fetchData(), 3000);
            } else {
                this._toast("Chyba při nahrávání.");
            }
        } catch (err) {
            console.error("Upload error:", err);
            this._toast("Chyba při nahrávání.");
        }
        this.uploading = false;
        e.target.value = "";
    }

    _toggleScanner() {
        this.showScanner = !this.showScanner;
        if (this.showScanner) {
            if (!scannerReady) {
                this._toast("Skener se ještě načítá, zkuste za chvíli…");
                this.showScanner = false;
                return;
            }
            setTimeout(() => this._startScanner(), 400);
        } else {
            this._stopScanner();
        }
    }

    _startScanner() {
        try {
            const el = this.shadowRoot.getElementById("reader");
            if (!el) return;
            this._scanner = new Html5Qrcode("reader");
            this._scanner.start(
                { facingMode: "environment" },
                { fps: 10, qrbox: { width: 250, height: 150 } },
                (text) => { this._toggleScanner(); this._addByEanValue(text); },
            ).catch(err => {
                console.error("Scanner error:", err);
                this._toast("Kamera není dostupná. Zkontrolujte HTTPS a oprávnění.");
                this.showScanner = false;
            });
        } catch (e) {
            console.error(e);
            this.showScanner = false;
        }
    }

    _stopScanner() {
        if (this._scanner) {
            try { this._scanner.stop(); } catch (_) {}
            this._scanner = null;
        }
    }

    _addByEan() {
        const input = this.shadowRoot.getElementById("ean-input");
        if (!input) return;
        this._addByEanValue(input.value.trim());
        input.value = "";
    }

    _addByEanValue(ean) {
        if (!ean) return;
        this.hass.callService("shopping_list_ocr", "add_item_by_ean", { ean });
        this._toast(`Hledám EAN: ${ean}…`);
        setTimeout(() => this._fetchData(), 2000);
    }

    _confirmReceipt(id) {
        this.hass.callService("shopping_list_ocr", "confirm_receipt", { receipt_id: id });
        this._toast("Položky přidány do skladu.");
        setTimeout(() => this._fetchData(), 1000);
    }

    _scanFolder() {
        this.hass.callService("shopping_list_ocr", "scan_folder", {});
        this._toast("Skenování složky spuštěno…");
        setTimeout(() => this._fetchData(), 5000);
    }

    _updateQty(name, delta) {
        const item = this.data.inventory[name];
        if (!item) return;
        const newQty = Math.max(0, item.quantity + delta);
        this.hass.callService("shopping_list_ocr", "update_inventory", {
            name,
            quantity: newQty,
            last_price: item.last_price || 0,
            unit: item.unit || "ks",
            image_url: item.image_url || "",
            store: item.store || "",
        });
        // Optimistic update
        item.quantity = newQty;
        this.requestUpdate();
    }

    _addRecipe() {
        const input = this.shadowRoot.getElementById("recipe-url");
        if (!input) return;
        const url = input.value.trim();
        if (!url) return;
        this.hass.callService("shopping_list_ocr", "add_recipe", { url });
        input.value = "";
        this._toast("Stahuji recept…");
        setTimeout(() => this._fetchData(), 5000);
    }

    _addIngredientsToList(recipe) {
        (recipe.ingredients || []).forEach(ing =>
            this.hass.callService("shopping_list", "add_item", { name: ing })
        );
        this._toast(`${recipe.ingredients?.length || 0} ingrediencí přidáno do nákupu.`);
    }

    _syncToKeep() {
        const u = this.shadowRoot.getElementById("keep-user")?.value || "";
        const p = this.shadowRoot.getElementById("keep-pass")?.value || "";
        const t = this.shadowRoot.getElementById("keep-title")?.value || "Nákup";
        if (!u || !p) { this._toast("Vyplňte e-mail a heslo."); return; }
        this.hass.callService("shopping_list_ocr", "sync_to_keep", { username: u, password: p, title: t });
        this._toast("Synchronizace spuštěna…");
    }
}

customElements.define("shopping-list-panel", ShoppingListPanel);
