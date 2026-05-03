import {
    LitElement,
    html,
    css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

class ShoppingListPanel extends LitElement {
    static get properties() {
        return {
            hass: { type: Object },
            narrow: { type: Boolean },
            route: { type: Object },
            panel: { type: Object },
            data: { type: Object },
            activeTab: { type: String },
        };
    }

    constructor() {
        super();
        this.data = { inventory: {}, pending_receipts: {}, recipes: {} };
        this.activeTab = 'inventory';
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
            .container {
                padding: 24px;
                max-width: 1200px;
                margin: 0 auto;
            }
            header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 32px;
            }
            h1 {
                font-weight: 300;
                font-size: 2.5rem;
                margin: 0;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .tabs {
                display: flex;
                gap: 16px;
                margin-bottom: 32px;
                border-bottom: 1px solid var(--divider-color);
                padding-bottom: 8px;
            }
            .tab {
                padding: 8px 16px;
                cursor: pointer;
                border-radius: 8px;
                font-weight: 500;
                transition: background 0.2s;
            }
            .tab.active {
                background: var(--accent-color);
                color: white;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 24px;
            }
            .card {
                background: var(--card-background-color, #fff);
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                overflow: hidden;
                transition: transform 0.2s;
                position: relative;
                display: flex;
                flex-direction: column;
            }
            .card:hover {
                transform: translateY(-4px);
            }
            .card-content {
                padding: 16px;
                display: flex;
                flex-direction: column;
                flex: 1;
            }
            .card-img {
                width: 100%;
                height: 160px;
                object-fit: cover;
                background: var(--secondary-background-color);
            }
            .store-badge {
                position: absolute;
                top: 12px;
                right: 12px;
                background: rgba(0,0,0,0.6);
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.7rem;
                font-weight: bold;
            }
            .receipt-card {
                border-left: 4px solid var(--accent-color);
            }
            .item-row {
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid var(--divider-color);
            }
            .item-name { font-weight: 500; }
            .item-price { color: var(--secondary-text-color); }
            
            .btn {
                background: var(--accent-color);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 500;
                margin-top: 12px;
                width: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }
            .btn-secondary {
                background: var(--secondary-background-color);
                color: var(--primary-text-color);
            }
            .btn-outline {
                background: transparent;
                border: 1px solid var(--accent-color);
                color: var(--accent-color);
            }
            
            .empty-state {
                text-align: center;
                padding: 40px;
                color: var(--secondary-text-color);
            }

            .recipe-form {
                background: var(--card-background-color);
                padding: 24px;
                border-radius: 12px;
                margin-bottom: 32px;
                display: flex;
                gap: 12px;
            }
            input {
                flex: 1;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid var(--divider-color);
                background: var(--primary-background-color);
                color: var(--primary-text-color);
            }
        `;
    }

    render() {
        const pendingCount = Object.keys(this.data.pending_receipts).length;
        const inventoryItems = Object.values(this.data.inventory);
        const recipes = Object.values(this.data.recipes || {});

        return html`
            <div class="container">
                <header>
                    <h1><ha-icon icon="mdi:cart-outline"></ha-icon> Nákupník</h1>
                </header>

                <div class="tabs">
                    <div class="tab ${this.activeTab === 'inventory' ? 'active' : ''}" @click=${() => this.activeTab = 'inventory'}>Sklad</div>
                    <div class="tab ${this.activeTab === 'receipts' ? 'active' : ''}" @click=${() => this.activeTab = 'receipts'}>Účtenky ${pendingCount > 0 ? `(${pendingCount})` : ''}</div>
                    <div class="tab ${this.activeTab === 'recipes' ? 'active' : ''}" @click=${() => this.activeTab = 'recipes'}>Recepty</div>
                </div>

                ${this.activeTab === 'inventory' ? this._renderInventory(inventoryItems) : ''}
                ${this.activeTab === 'receipts' ? this._renderReceipts() : ''}
                ${this.activeTab === 'recipes' ? this._renderRecipes(recipes) : ''}
            </div>
        `;
    }

    _renderInventory(items) {
        return html`
            <section>
                ${items.length === 0 ? html`
                    <div class="empty-state">Sklad je prázdný. Nahrajte účtenku a spusťte skenování.</div>
                ` : html`
                    <div class="grid">
                        ${items.map(item => html`
                            <div class="card">
                                ${item.image_url ? html`
                                    <img class="card-img" src="${item.image_url}" alt="${item.name}" onerror="this.style.display='none'">
                                ` : ''}
                                ${item.store ? html`<div class="store-badge">${item.store}</div>` : ''}
                                <div class="card-content">
                                    <h3 style="margin: 0">${item.name}</h3>
                                    <div style="font-size: 1.5rem; font-weight: bold; margin: 8px 0">
                                        ${item.quantity} <span style="font-size: 0.9rem; font-weight: normal">${item.unit}</span>
                                    </div>
                                    <div class="item-price">Poslední cena: ${item.last_price} Kč</div>
                                    <div style="display: flex; gap: 8px; margin-top: auto">
                                        <button class="btn btn-secondary" @click=${() => this._updateQty(item.name, -1)}>-1</button>
                                        <button class="btn btn-secondary" @click=${() => this._updateQty(item.name, 1)}>+1</button>
                                    </div>
                                </div>
                            </div>
                        `)}
                    </div>
                `}
            </section>
        `;
    }

    _renderReceipts() {
        const receipts = Object.values(this.data.pending_receipts);
        return html`
            <section>
                ${receipts.length === 0 ? html`
                    <div class="empty-state">Žádné nové účtenky k potvrzení.</div>
                ` : html`
                    <div class="grid">
                        ${receipts.map(receipt => html`
                            <div class="card receipt-card">
                                ${receipt.store ? html`<div class="store-badge">${receipt.store}</div>` : ''}
                                <div class="card-content">
                                    <div style="font-size: 0.8rem; color: var(--secondary-text-color)">
                                        ${new Date(receipt.date).toLocaleString()}
                                    </div>
                                    <div style="margin: 12px 0">
                                        ${receipt.items.map(item => html`
                                            <div class="item-row">
                                                <div style="display: flex; align-items: center; gap: 8px">
                                                    ${item.image_url ? html`<img src="${item.image_url}" style="width: 24px; height: 24px; border-radius: 4px">` : ''}
                                                    <span class="item-name">${item.name}</span>
                                                </div>
                                                <span class="item-price">${item.price} Kč</span>
                                            </div>
                                        `)}
                                    </div>
                                    <button class="btn" @click=${() => this._confirmReceipt(receipt.id)}>
                                        Potvrdit a přidat do skladu
                                    </button>
                                </div>
                            </div>
                        `)}
                    </div>
                `}
            </section>
        `;
    }

    _renderRecipes(recipes) {
        return html`
            <section>
                <div class="recipe-form">
                    <input id="recipe-url" type="text" placeholder="Vložte odkaz na recept (např. z Toprecepty.cz)">
                    <button class="btn" style="width: auto; margin: 0" @click=${this._addRecipe}>Přidat recept</button>
                </div>

                ${recipes.length === 0 ? html`
                    <div class="empty-state">Zatím nemáte žádné uložené recepty.</div>
                ` : html`
                    <div class="grid">
                        ${recipes.map(recipe => html`
                            <div class="card">
                                ${recipe.image_url ? html`
                                    <img class="card-img" src="${recipe.image_url}" alt="${recipe.title}" onerror="this.style.display='none'">
                                ` : ''}
                                <div class="card-content">
                                    <h3 style="margin: 0">${recipe.title}</h3>
                                    <div style="font-size: 0.8rem; color: var(--secondary-text-color); margin-bottom: 12px">
                                        Přidáno: ${new Date(recipe.added_at).toLocaleDateString()}
                                    </div>
                                    <div style="margin-bottom: 12px; flex: 1; font-size: 0.9rem">
                                        <strong>Ingredience:</strong> ${recipe.ingredients.length} položek
                                    </div>
                                    <div style="display: flex; flex-direction: column; gap: 8px">
                                        <a href="${recipe.pdf_url}" target="_blank" class="btn btn-outline" style="text-decoration: none">
                                            <ha-icon icon="mdi:file-pdf-box"></ha-icon> Otevřít PDF
                                        </a>
                                        <button class="btn" @click=${() => this._addIngredientsToShoppingList(recipe)}>
                                            <ha-icon icon="mdi:playlist-plus"></ha-icon> Přidat do nákupu
                                        </button>
                                    </div>
                                </div>
                            </div>
                        `)}
                    </div>
                `}
            </section>
        `;
    }

    _confirmReceipt(id) {
        this.hass.callService("shopping_list_ocr", "confirm_receipt", { receipt_id: id });
    }

    _updateQty(name, delta) {
        const item = this.data.inventory[name];
        this.hass.callService("shopping_list_ocr", "update_inventory", {
            name: name,
            quantity: Math.max(0, item.quantity + delta),
            last_price: item.last_price,
            unit: item.unit,
            image_url: item.image_url,
            store: item.store
        });
    }

    _addRecipe() {
        const input = this.shadowRoot.getElementById('recipe-url');
        const url = input.value.strip ? input.value.strip() : input.value.trim();
        if (!url) return;
        this.hass.callService("shopping_list_ocr", "add_recipe", { url: url });
        input.value = "";
        this.hass.bus.async_fire("hass-notification", { message: "Stahuji recept..." });
    }

    _addIngredientsToShoppingList(recipe) {
        recipe.ingredients.forEach(ing => {
            this.hass.callService("shopping_list", "add_item", { name: ing });
        });
        this.hass.bus.async_fire("hass-notification", { message: `Ingredience k receptu '${recipe.title}' přidány do seznamu.` });
    }
}

customElements.define("shopping-list-panel", ShoppingListPanel);
