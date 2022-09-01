import urllib.request

db_url = "https://github.com/quadratecode/eledmg-db/raw/main/eledmg_data_ch.sqlite"

urllib.request.urlretrieve(db_url, "eledmg_data_ch.sqlite")
