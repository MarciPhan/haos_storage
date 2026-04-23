# Home Assistant Bookcase Integration

A custom integration for Home Assistant to manage your personal book library.

## Features
- **Add books by ISBN**: Automatically fetches metadata (title, authors, cover) from Open Library API.
- **Track Status**: Keep track of books you want to read, are currently reading, or have finished.
- **Ratings & Notes**: Rate your books and add personal notes.
- **Lending Tracker**: Keep track of who you lent your books to.
- **Statistics**: Built-in sensors for total books, read books, etc.

## Installation
1. Copy the `custom_components/bookcase` directory to your HA `config` directory.
2. Restart Home Assistant.
3. Add the "Knihovnička" integration via the UI (Settings -> Devices & Services).

## Services
- `bookcase.add_by_isbn`: Add a book using its ISBN.
- `bookcase.update_book`: Update status, rating, or notes.
- `bookcase.delete_book`: Remove a book from the library.

## License
MIT
