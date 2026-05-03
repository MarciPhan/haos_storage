import {
    LitElement,
    html,
    css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

const script = document.createElement('script');
script.src = "https://unpkg.com/html5-qrcode";
document.head.appendChild(script);

class ShoppingListPanel extends LitElement {
    static get properties() {
        return {
            hass: { type: Object },
            data: { type: Object },
            activeTab: { type: String },
            showScanner: { type: Boolean },
        };
    }

    constructor() {
        super();
        this.data = { inventory: {}, pending_receipts: {}, recipes: {}, keep_config: {} };
        this.activeTab = 'inventory';
        this.showScanner = false;
        this.html5QrCode = null;
    }

    connectedCallback() {
        super.connectedCallback();
        this._fetchData();
        if (this.hass) {
            this.hass.connection.subscribeEvents(() => this._fetchData(), "shopping_list_ocr_updated");
        }
    }

    async _fetchData() {
        if (!this.hass) return;
        try {
            const response = await this.hass.fetchWithAuth("/api/shopping_list/data");
            if (response.ok) {
                this.data = await response.json();
            }
        } catch (err) {
            console.error("Failed to fetch shopping list data:", err);
        }
    }

    static get styles() {
        return css`
            :host {
                background-color: var(--primary-background-color);
                display: block;
                height: 100vh;
                font-family: 'Roboto', sans-serif;
                color: var(--primary-text-color);
            }
            .container { padding: 24px; max-width: 1200px; margin: 0 auto; }
            header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }
            h1 { font-weight: 300; font-size: 2.5rem; margin: 0; display: flex; align-items: center; gap: 12px; }
            .tabs { display: flex; gap: 16px; margin-bottom: 32px; border-bottom: 1px solid var(--divider-color); padding-bottom: 8px; }
            .tab { padding: 8px 16px; cursor: pointer; border-radius: 8px; font-weight: 500; transition: background 0.2s; }
            .tab.active { background: var(--accent-color); color: white; }
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px; }
            .card { background: var(--card-background-color, #fff); border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); overflow: hidden; transition: transform 0.2s; position: relative; display: flex; flex-direction: column; }
            .card:hover { transform: translateY(-4px); }
            .card-content { padding: 16px; display: flex; flex-direction: column; flex: 1; }
            .card-img { width: 100%; height: 160px; object-fit: cover; background: var(--secondary-background-color); }
            .btn { background: var(--accent-color); color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 500; margin-top: 12px; width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px; }
            .btn-secondary { background: var(--secondary-background-color); color: var(--primary-text-color); }
            .btn-outline { background: transparent; border: 1px solid var(--accent-color); color: var(--accent-color); }
            .toolbar { background: var(--card-background-color); padding: 16px 24px; border-radius: 12px; margin-bottom: 32px; display: flex; align-items: center; gap: 16px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
            input { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--primary-background-color); color: var(--primary-text-color); }
            .modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 9999; padding: 20px; }
            #reader { width: 100%; max-width: 500px; background: white; border-radius: 12px; overflow: hidden; }
            .modal-close { margin-top: 20px; padding: 10px 30px; background: white; color: black; border-radius: 30px; font-weight: bold; cursor: pointer; }
            
            .config-form { max-width: 500px; margin: 0 auto; background: var(--card-background-color); padding: 32px; border-radius: 16px; display: flex; flex-direction: column; gap: 16px; }
        `;
    }

    render() {
        return html`
            <div class="container">
                <header>
                    <h1><ha-icon icon="mdi:cart-outline"></ha-icon> Nákupník</h1>
                    <div style="display: flex; gap: 8px">
                        <button class="btn" style="width: auto; margin: 0" @click=${this._toggleScanner}>
                            <ha-icon icon="mdi:barcode-scan"></ha-icon> Skenovat EAN
                        </button>
                    </div>
                </header>

                <div class="tabs">
                    <div class="tab ${this.activeTab === 'inventory' ? 'active' : ''}" @click=${() => this.activeTab = 'inventory'}>Sklad</div>
                    <div class="tab ${this.activeTab === 'receipts' ? 'active' : ''}" @click=${() => this.activeTab = 'receipts'}>Účtenky</div>
                    <div class="tab ${this.activeTab === 'recipes' ? 'active' : ''}" @click=${() => this.activeTab = 'recipes'}>Recepty</div>
                    <div class="tab ${this.activeTab === 'sync' ? 'active' : ''}" @click=${() => this.activeTab = 'sync'}>Synchronizace</div>
                </div>

                ${this.activeTab === 'inventory' ? this._renderInventory() : ''}
                ${this.activeTab === 'receipts' ? this._renderReceipts() : ''}
                ${this.activeTab === 'recipes' ? this._renderRecipes() : ''}
                ${this.activeTab === 'sync' ? this._renderSync() : ''}

                ${this.showScanner ? html`
                    <div class="modal">
                        <div id="reader"></div>
                        <div class="modal-close" @click=${this._toggleScanner}>Zavřít skener</div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    _renderInventory() {
        const items = Object.values(this.data.inventory);
        return html`
            <section>
                <div class="toolbar">
                    <input id="ean-input" type="text" placeholder="Zadejte EAN kód ručně...">
                    <button class="btn" style="width: auto; margin: 0" @click=${this._addByEan}>Přidat podle EAN</button>
                </div>
                <div class="grid">
                    ${items.map(item => html`
                        <div class="card">
                            ${item.image_url ? html`<img class="card-img" src="${item.image_url}">` : ''}
                            <div class="card-content">
                                <h3 style="margin: 0">${item.name}</h3>
                                <div style="font-size: 1.5rem; font-weight: bold; margin: 8px 0">${item.quantity} ${item.unit}</div>
                                <div style="display: flex; gap: 8px; margin-top: auto">
                                    <button class="btn btn-secondary" @click=${() => this._updateQty(item.name, -1)}>-1</button>
                                    <button class="btn btn-secondary" @click=${() => this._updateQty(item.name, 1)}>+1</button>
                                </div>
                            </div>
                        </div>
                    `)}
                </div>
            </section>
        `;
    }

    _renderReceipts() {
        const receipts = Object.values(this.data.pending_receipts);
        return html`
            <section>
                <div class="toolbar">
                    <div style="flex: 1">Nahrajte novou účtenku:</div>
                    <input type="file" id="file-upload" style="display: none" accept="image/*" @change=${this._handleUpload}>
                    <button class="btn" style="width: auto; margin: 0" @click=${() => this.shadowRoot.getElementById('file-upload').click()}>
                        <ha-icon icon="mdi:upload"></ha-icon> Nahrát účtenku
                    </button>
                </div>
                <div class="grid">
                    ${receipts.map(receipt => html`
                        <div class="card">
                            <div class="card-content">
                                <div>${new Date(receipt.date).toLocaleString()}</div>
                                <div style="margin: 10px 0">
                                    ${receipt.items.map(i => html`<div>${i.name} - ${i.price} Kč</div>`)}
                                </div>
                                <button class="btn" @click=${() => this._confirmReceipt(receipt.id)}>Potvrdit</button>
                            </div>
                        </div>
                    `)}
                </div>
            </section>
        `;
    }

    _renderRecipes() {
        const recipes = Object.values(this.data.recipes);
        return html`
            <section>
                <div class="toolbar">
                    <input id="recipe-url" type="text" placeholder="URL receptu...">
                    <button class="btn" style="width: auto; margin: 0" @click=${this._addRecipe}>Přidat recept</button>
                </div>
                <div class="grid">
                    ${recipes.map(r => html`
                        <div class="card">
                            ${r.image_url ? html`<img class="card-img" src="${r.image_url}">` : ''}
                            <div class="card-content">
                                <h3>${r.title}</h3>
                                <a href="${r.pdf_url}" target="_blank" class="btn btn-outline">Otevřít PDF</a>
                                <button class="btn" @click=${() => this._addIngredientsToShoppingList(r)}>Do nákupu</button>
                            </div>
                        </div>
                    `)}
                </div>
            </section>
        `;
    }

    _renderSync() {
        const config = this.data.keep_config || {};
        return html`
            <section>
                <div class="config-form">
                    <h2 style="margin: 0">Nastavení Google Keep</h2>
                    <p style="font-size: 0.9rem; color: var(--secondary-text-color)">Použijte "Heslo aplikace" z nastavení Google účtu.</p>
                    <input id="keep-user" type="text" placeholder="Google E-mail" .value="${config.username || ''}">
                    <input id="keep-pass" type="password" placeholder="App Password" .value="${config.password || ''}">
                    <input id="keep-title" type="text" placeholder="Název poznámky v Keep" .value="${config.title || 'Nákup'}">
                    <button class="btn" @click=${this._syncToKeep}>
                        <ha-icon icon="mdi:sync"></ha-icon> Synchronizovat nyní
                    </button>
                </div>
            </section>
        `;
    }

    _syncToKeep() {
        const username = this.shadowRoot.getElementById('keep-user').value;
        const password = this.shadowRoot.getElementById('keep-pass').value;
        const title = this.shadowRoot.getElementById('keep-title').value;
        
        this.hass.callService("shopping_list_ocr", "sync_to_keep", {
            username: username,
            password: password,
            title: title
        });
        this.hass.bus.async_fire("hass-notification", { message: "Synchronizace s Google Keep spuštěna..." });
    }

    async _handleUpload(e) {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        this.hass.bus.async_fire("hass-notification", { message: "Nahrávám účtenku..." });
        try {
            const response = await this.hass.fetchWithAuth("/api/shopping_list/upload", { method: "POST", body: formData });
            if (response.ok) { this.hass.bus.async_fire("hass-notification", { message: "Zpracovávám..." }); setTimeout(() => this._fetchData(), 2000); }
        } catch (err) { console.error("Upload failed:", err); }
    }

    _toggleScanner() {
        this.showScanner = !this.showScanner;
        if (this.showScanner) setTimeout(() => this._startScanner(), 500);
        else if (this.html5QrCode) this.html5QrCode.stop();
    }

    _startScanner() {
        this.html5QrCode = new Html5Qrcode("reader");
        this.html5QrCode.start({ facingMode: "environment" }, { fps: 10, qrbox: { width: 250, height: 150 } }, (decodedText) => {
            this._toggleScanner(); this._addByEanValue(decodedText);
        });
    }

    _addByEan() { const input = this.shadowRoot.getElementById('ean-input'); this._addByEanValue(input.value.trim()); input.value = ""; }
    _addByEanValue(ean) { if (!ean) return; this.hass.callService("shopping_list_ocr", "add_item_by_ean", { ean: ean }); }
    _confirmReceipt(id) { this.hass.callService("shopping_list_ocr", "confirm_receipt", { receipt_id: id }); }
    _scanFolder() { this.hass.callService("shopping_list_ocr", "scan_folder", {}); }
    _updateQty(name, delta) {
        const item = this.data.inventory[name];
        this.hass.callService("shopping_list_ocr", "update_inventory", {
            name: name, quantity: Math.max(0, item.quantity + delta), last_price: item.last_price, unit: item.unit, image_url: item.image_url
        });
    }
    _addRecipe() { const input = this.shadowRoot.getElementById('recipe-url'); this.hass.callService("shopping_list_ocr", "add_recipe", { url: input.value.trim() }); input.value = ""; }
    _addIngredientsToShoppingList(recipe) { recipe.ingredients.forEach(ing => this.hass.callService("shopping_list", "add_item", { name: ing })); }
}

customElements.define("shopping-list-panel", ShoppingListPanel);
