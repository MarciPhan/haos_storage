class BookcasePanel extends HTMLElement {
  constructor() {
    super();
    this._loading = false;
  }

  set hass(hass) {
    const oldBooks = this._hass?.states['sensor.bookcase_total_books']?.attributes?.books;
    this._hass = hass;
    const newBooks = hass.states['sensor.bookcase_total_books']?.attributes?.books;

    if (!this.content) {
      this.initStructure();
    }

    // Update if books changed
    if (JSON.stringify(oldBooks) !== JSON.stringify(newBooks)) {
      this._loading = false;
      this.render();
      this.updateAddButton();
    }
  }

  initStructure() {
    this.innerHTML = `
      <style>
        :host {
          background-color: var(--primary-background-color);
          display: block;
          height: 100%;
          color: var(--primary-text-color);
          font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        }
        .container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 32px 16px;
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 40px;
        }
        .header h1 {
          margin: 0;
          font-size: 2.5rem;
          font-weight: 800;
          background: linear-gradient(135deg, var(--primary-color), #ff9800);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .stats-chip {
          background: var(--secondary-background-color);
          padding: 8px 16px;
          border-radius: 20px;
          font-weight: 500;
          font-size: 0.9rem;
          border: 1px solid var(--divider-color);
        }
        
        .add-box {
          display: flex;
          gap: 12px;
          background: var(--card-background-color);
          padding: 8px;
          border-radius: 16px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.1);
          margin-bottom: 48px;
          border: 1px solid var(--divider-color);
        }
        input {
          background: transparent;
          color: var(--primary-text-color);
          border: none;
          padding: 12px 20px;
          flex-grow: 1;
          font-size: 16px;
          outline: none;
        }
        button#add-btn {
          background: var(--primary-color);
          color: white;
          border: none;
          padding: 12px 24px;
          border-radius: 12px;
          cursor: pointer;
          font-weight: bold;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        button#add-btn:hover:not(:disabled) { 
          transform: translateY(-2px);
          box-shadow: 0 4px 12px var(--primary-color);
        }
        button#add-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
          gap: 32px;
        }
        .book-card {
          background: var(--card-background-color);
          border-radius: 16px;
          padding: 12px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.05);
          transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
          position: relative;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          border: 1px solid transparent;
        }
        .book-card:hover {
          transform: translateY(-10px);
          box-shadow: 0 12px 30px rgba(0,0,0,0.15);
          border-color: var(--primary-color);
        }
        .cover-wrapper {
          position: relative;
          width: 100%;
          aspect-ratio: 2/3;
          border-radius: 10px;
          overflow: hidden;
          background: var(--secondary-background-color);
        }
        .book-card img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          transition: transform 0.5s;
        }
        .book-card:hover img {
          transform: scale(1.05);
        }
        .book-title {
          font-weight: 700;
          margin-top: 14px;
          font-size: 0.95rem;
          line-height: 1.3;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
          min-height: 2.6rem;
        }
        .book-author {
          font-size: 0.8rem;
          color: var(--secondary-text-color);
          margin-top: 4px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        
        .delete-btn {
          position: absolute;
          top: -10px;
          right: -10px;
          background: #ff5252;
          color: white;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          border: 2px solid var(--card-background-color);
          opacity: 0;
          transition: opacity 0.2s, transform 0.2s;
          z-index: 2;
        }
        .book-card:hover .delete-btn {
          opacity: 1;
        }
        .delete-btn:hover {
          transform: scale(1.1);
          background: #ff1744;
        }

        .status-badge {
          position: absolute;
          bottom: 8px;
          left: 8px;
          background: rgba(0,0,0,0.6);
          backdrop-filter: blur(4px);
          color: white;
          padding: 3px 8px;
          border-radius: 6px;
          font-size: 0.6rem;
          font-weight: bold;
          text-transform: uppercase;
        }

        /* Modal Styles */
        .modal {
          display: none;
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0,0,0,0.8);
          backdrop-filter: blur(8px);
          z-index: 1000;
          align-items: center;
          justify-content: center;
          padding: 20px;
        }
        .modal.open { display: flex; }
        .modal-content {
          background: var(--card-background-color);
          max-width: 800px;
          width: 100%;
          border-radius: 24px;
          position: relative;
          display: flex;
          overflow: hidden;
          box-shadow: 0 25px 50px rgba(0,0,0,0.5);
          animation: modalSlide 0.3s ease-out;
        }
        @keyframes modalSlide {
          from { transform: translateY(30px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .modal-close {
          position: absolute;
          top: 20px;
          right: 20px;
          cursor: pointer;
          background: var(--secondary-background-color);
          width: 40px;
          height: 40px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          z-index: 10;
        }
        .modal-body {
          display: flex;
          width: 100%;
        }
        .modal-cover {
          width: 300px;
          flex-shrink: 0;
          background: var(--secondary-background-color);
        }
        .modal-cover img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
        .modal-info {
          padding: 40px;
          flex-grow: 1;
          display: flex;
          flex-direction: column;
        }
        .modal-info h2 { margin-top: 0; font-size: 2rem; margin-bottom: 8px; }
        .modal-info .author { font-size: 1.2rem; color: var(--primary-color); margin-bottom: 24px; }
        .modal-details {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
          margin-bottom: 30px;
        }
        .detail-item label { display: block; font-size: 0.8rem; color: var(--secondary-text-color); margin-bottom: 4px; }
        .detail-item span { font-weight: 500; }
        
        .loading-spinner {
          display: none;
          width: 20px;
          height: 20px;
          border: 3px solid rgba(255,255,255,0.3);
          border-radius: 50%;
          border-top-color: #fff;
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        @media (max-width: 600px) {
          .modal-body { flex-direction: column; }
          .modal-cover { width: 100%; height: 300px; }
          .modal-content { max-height: 90vh; overflow-y: auto; }
        }
      </style>
      
      <div class="container">
        <div class="header">
          <h1>📚 Moje Knihovna</h1>
          <div id="stats" class="stats-chip">Načítám...</div>
        </div>
        
        <div class="add-box">
          <input type="text" id="isbn-input" placeholder="Napište ISBN kód knihy...">
          <button id="add-btn">
            <span class="loading-spinner" id="btn-spinner"></span>
            <span id="btn-text">Přidat knihu</span>
          </button>
        </div>

        <div class="grid" id="book-grid">
          <!-- Knihy se vykreslí sem -->
        </div>
      </div>

      <div id="book-modal" class="modal">
        <div class="modal-content">
          <div class="modal-close">&times;</div>
          <div class="modal-body" id="modal-body"></div>
        </div>
      </div>
    `;

    this.content = this.querySelector('#book-grid');
    this.input = this.querySelector('#isbn-input');
    this.addBtn = this.querySelector('#add-btn');
    this.modal = this.querySelector('#book-modal');
    this.modalClose = this.querySelector('.modal-close');

    this.addBtn.onclick = () => this.handleAdd();
    this.input.onkeypress = (e) => { if (e.key === 'Enter') this.handleAdd(); };
    this.modalClose.onclick = () => this.modal.classList.remove('open');
    this.modal.onclick = (e) => { if (e.target === this.modal) this.modal.classList.remove('open'); };
  }

  handleAdd() {
    const isbn = this.input.value.trim();
    if (isbn && !this._loading) {
      this._loading = true;
      this.updateAddButton();
      this._hass.callService('bookcase', 'add_by_isbn', { isbn });
      this.input.value = '';
    }
  }

  updateAddButton() {
    const btnText = this.querySelector('#btn-text');
    const spinner = this.querySelector('#btn-spinner');
    if (this._loading) {
      this.addBtn.disabled = true;
      btnText.innerText = 'Stahuji...';
      spinner.style.display = 'block';
    } else {
      this.addBtn.disabled = false;
      btnText.innerText = 'Přidat knihu';
      spinner.style.display = 'none';
    }
  }

  deleteBook(e, bookId) {
    e.stopPropagation();
    if (confirm('Opravdu chcete tuto knihu smazat z knihovny?')) {
      this._hass.callService('bookcase', 'delete_book', { book_id: bookId });
    }
  }

  openDetail(book) {
    const body = this.querySelector('#modal-body');
    const authors = book.authors ? book.authors.join(', ') : 'Neznámý autor';
    const genres = book.genre ? (Array.isArray(book.genre) ? book.genre.join(', ') : book.genre) : 'Nezadáno';
    
    body.innerHTML = `
      <div class="modal-cover">
        <img src="${book.cover_url || ''}" onerror="this.src='https://via.placeholder.com/400x600?text=Bez+obalky'" alt="${book.title}">
      </div>
      <div class="modal-info">
        <h2>${book.title}</h2>
        <div class="author">${authors}</div>
        
        <div class="modal-details">
          <div class="detail-item">
            <label>ISBN</label>
            <span>${book.isbn}</span>
          </div>
          <div class="detail-item">
            <label>Vydavatel</label>
            <span>${book.publisher || 'Neznámý'}</span>
          </div>
          <div class="detail-item">
            <label>Rok vydání</label>
            <span>${book.year || 'Neznámý'}</span>
          </div>
          <div class="detail-item">
            <label>Počet stran</label>
            <span>${book.page_count || '?'}</span>
          </div>
          <div class="detail-item">
            <label>Jazyk</label>
            <span>${book.language || 'Neznámý'}</span>
          </div>
          <div class="detail-item">
            <label>Žánry</label>
            <span>${genres}</span>
          </div>
        </div>
        
        <div style="margin-top: auto;">
          <div class="detail-item">
            <label>Poznámky</label>
            <p>${book.notes || 'Žádné poznámky...'}</p>
          </div>
        </div>
      </div>
    `;
    this.modal.classList.add('open');
  }

  render() {
    const state = this._hass.states['sensor.bookcase_total_books'];
    if (!state || !state.attributes.books) {
      this.content.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; opacity: 0.5;">Knihovna je prázdná...</div>';
      return;
    }

    const books = state.attributes.books;
    this.querySelector('#stats').innerText = `Celkem: ${books.length} knih`;
    
    if (books.length === 0) {
      this.content.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; opacity: 0.5;">Zatím jste nepřidali žádné knihy.</div>';
      return;
    }

    this.content.innerHTML = '';
    
    [...books].reverse().forEach(book => {
      const card = document.createElement('div');
      card.className = 'book-card';
      card.onclick = () => this.openDetail(book);
      
      const statusText = book.status === 'to_read' ? 'CHCI PŘEČÍST' : (book.status === 'reading' ? 'ROZEČTENO' : 'PŘEČTENO');
      const authors = book.authors ? book.authors.join(', ') : 'Neznámý autor';
      
      const coverUrl = book.cover_url || '';
      card.innerHTML = `
        <div class="delete-btn" title="Smazat knihu">&times;</div>
        <div class="cover-wrapper">
          ${coverUrl ? `
            <img src="${coverUrl}" 
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" 
                 alt="${book.title}">
          ` : ''}
          <div style="${coverUrl ? 'display:none;' : 'display:flex;'} width:100%; height:100%; align-items:center; justify-content:center; flex-direction:column; background:var(--secondary-background-color); color:var(--secondary-text-color); font-size:10px; text-align:center; padding:10px;">
            <span style="font-size:24px; margin-bottom:5px;">📖</span>
            <div style="font-weight:bold; overflow:hidden; text-overflow:ellipsis; width:100%;">${book.title}</div>
          </div>
          <div class="status-badge">${statusText}</div>
        </div>
        <div class="book-title">${book.title}</div>
        <div class="book-author">${authors}</div>
      `;
      
      card.querySelector('.delete-btn').onclick = (e) => this.deleteBook(e, book.id);
      this.content.appendChild(card);
    });
  }
}
customElements.define('bookcase-panel', BookcasePanel);
