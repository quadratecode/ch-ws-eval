import urllib.request

db_url = "https://github.com/quadratecode/eledmg-db/raw/main/ch_ws_db.sqlite"

urllib.request.urlretrieve(db_url, "ch_ws_db.sqlite")
