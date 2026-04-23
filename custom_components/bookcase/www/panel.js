class BookcasePanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
      this.innerHTML = `
        <style>
          :host {
            background-color: var(--primary-background-color);
            display: block;
            height: 100%;
            padding: 24px;
            color: var(--primary-text-color);
            font-family: var(--paper-font-body1_-_font-family);
          }
          .container {
            max-width: 1200px;
            margin: 0 auto;
          }
          .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            border-bottom: 1px solid var(--divider-color);
            padding-bottom: 16px;
          }
          .add-box {
            display: flex;
            gap: 10px;
            background: var(--card-background-color);
            padding: 15px;
            border-radius: 12px;
            box-shadow: var(--ha-card-box-shadow);
            margin-bottom: 32px;
          }
          input {
            background: var(--input-background-color, var(--secondary-background-color));
            color: var(--primary-text-color);
            border: 1px solid var(--divider-color);
            padding: 10px 15px;
            border-radius: 8px;
            flex-grow: 1;
            font-size: 16px;
          }
          button {
            background: var(--primary-color);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: opacity 0.2s;
          }
          button:hover { opacity: 0.8; }
          .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 25px;
          }
          .book-card {
            background: var(--card-background-color);
            border-radius: 12px;
            padding: 12px;
            box-shadow: var(--ha-card-box-shadow);
            transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            position: relative;
            cursor: pointer;
          }
          .book-card:hover {
            transform: translateY(-8px);
          }
          .book-card img {
            width: 100%;
            aspect-ratio: 2/3;
            object-fit: cover;
            border-radius: 8px;
            background: var(--secondary-background-color);
          }
          .book-title {
            font-weight: bold;
            margin-top: 12px;
            font-size: 1rem;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
          }
          .book-author {
            font-size: 0.85rem;
            color: var(--secondary-text-color);
            margin-top: 4px;
          }
          .status-badge {
            position: absolute;
            top: 20px;
            right: 20px;
            background: var(--primary-color);
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: bold;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
          }
        </style>
        <div class="container">
          <div class="header">
            <h1>📚 Knihovnička</h1>
            <div id="stats"></div>
          </div>
          
          <div class="add-box">
            <input type="text" id="isbn-input" placeholder="Zadejte ISBN kód (např. 9788090024069)">
            <button id="add-btn">Přidat knihu</button>
          </div>

          <div class="grid" id="book-grid">
            <!-- Knihy se vykreslí sem -->
          </div>
        </div>
      `;
      this.content = this.querySelector('#book-grid');
      this.input = this.querySelector('#isbn-input');
      this.addBtn = this.querySelector('#add-btn');
      
      this.addBtn.onclick = () => {
        const isbn = this.input.value.trim();
        if (isbn) {
          this._hass.callService('bookcase', 'add_by_isbn', { isbn });
          this.input.value = '';
        }
      };
    }

    this.render();
  }

  render() {
    const state = this._hass.states['sensor.bookcase_total_books'];
    if (!state || !state.attributes.books) return;

    const books = state.attributes.books;
    this.querySelector('#stats').innerText = `Celkem: ${books.length} knih`;
    
    this.content.innerHTML = books.map(book => `
      <div class="book-card">
        <div class="status-badge">${book.status === 'to_read' ? 'CHCI PŘEČÍST' : 'ROZEČTENO'}</div>
        <img src="${book.cover_url || 'https://via.placeholder.com/200x300?text=Bez+obalky'}" alt="${book.title}">
        <div class="book-title">${book.title}</div>
        <div class="book-author">${book.authors ? book.authors.join(', ') : 'Neznámý autor'}</div>
      </div>
    `).reverse().join('');
  }
}
customElements.define('bookcase-panel', BookcasePanel);
