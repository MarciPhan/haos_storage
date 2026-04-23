"""Constants for the Bookcase integration."""

DOMAIN = "bookcase"
STORAGE_KEY = "bookcase.storage"
STORAGE_VERSION = 1

CONF_ISBN = "isbn"
CONF_TITLE = "title"
CONF_AUTHOR = "author"
CONF_STATUS = "status"
CONF_RATING = "rating"
CONF_NOTES = "notes"
CONF_LENT_TO = "lent_to"

STATUS_TO_READ = "to_read"
STATUS_READING = "reading"
STATUS_READ = "read"

BOOK_STATUSES = [STATUS_TO_READ, STATUS_READING, STATUS_READ]
