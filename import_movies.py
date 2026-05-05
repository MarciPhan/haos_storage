import json
import uuid
import os

# Path to the HA storage for movie_tracker
STORAGE_PATH = "/home/marcipan/Dokumenty/test/HAos/.storage/movie_tracker_data"

# The big list from the user
MOVIE_LIST = """
Hunger games
Pán prstenů
Hobit
Lásky čas
Dálnice 60
Noc na Karlštejně
Mulan
Frozen
Pearl Harbor
One piece (seriál)
Past na rodiče
BBC Sherlock Holmes
Musíme si pomáhat
Pasažéři
Piráti z Karibiku
Lego movie 1 a 2
Bohové musí být šílení
Gladiator
Poslední samurai
Vlny
Luck
Kouzla králů
Rudá jako rubín série
Harry potter celá série
Tajemství staré Bambitka
Na vlásku
Mamma Mia 2
Zataženo, občas trakaře
Titanic
StarWars
Chipmunci
Papírový dům
Marley & já
Monty pythons
Rebelka
Kingsman
Noc v muzeu
Hvězdný prach
Legenda o sovích strážcích
Vlkochodci
Koralína
Stmívání
Až odpadá listí z dubu
Sedmero krkavců
Lichožrouti
Narnie
Hříšný tanec
Tančím, abych žil
Obsluhoval jsem anglického krále
Luther
Pelíšky
La casa de papel
Annabel
Wall-e
Zootopie
Robinsonovi
John Wick
Aladin
Stranger things
Čarodějův učeň
Pí a jeho život
Drž hubu
The promised neverland
Volání divočiny
Hvězdy nám nepřály
Dárce
Steve Kinga
Lalala land
Jak vycvičili draka
Mamma mia 1
D&D film
Nedotknutelní
Jak vycvičili draka 3
Věřte nevěřte
Hačikó
Mentalista (seriál)
Divergence
""".strip().split("\n")

def import_movies():
    if not os.path.exists(STORAGE_PATH):
        print(f"Storage file not found at {STORAGE_PATH}. Initializing new one.")
        data = {"data": {"watched": {}, "wishlist": {}, "history": [], "settings": {"language": "CZ"}}, "version": 1, "key": "movie_tracker_data"}
    else:
        with open(STORAGE_PATH, "r") as f:
            data = json.load(f)

    wishlist = data["data"]["wishlist"]
    
    for title in MOVIE_LIST:
        title = title.strip()
        if not title: continue
        
        # Check if already in wishlist or watched
        exists = any(m["title"].lower() == title.lower() for m in wishlist.values())
        if not exists:
            movie_id = str(uuid.uuid4())
            wishlist[movie_id] = {
                "id": movie_id,
                "title": title,
                "type": "series" if "seriál" in title.lower() or "série" in title.lower() else "movie",
                "image": "https://via.placeholder.com/300x450?text=" + title.replace(" ", "+"),
                "url": "", # No CSFD URL yet, search will fill it when clicked
                "added_at": "2024-05-04T19:00:00"
            }
            print(f"Added: {title}")

    with open(STORAGE_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print("Import finished!")

if __name__ == "__main__":
    import_movies()
