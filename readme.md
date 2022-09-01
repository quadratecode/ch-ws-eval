# About

A simple prototype to request wind speeds from the database residing in [this repo](https://github.com/quadratecode/eledmg-db). Made with [PyWebIO](https://github.com/pywebio/PyWebIO).

# Get started

Set up:
```
git clone https://github.com/quadratecode/eledmg-checker
pip3 install -r requirements.txt
```
Update database manually or via cron:
```
python3 db_crawler.py
```
Start PyWebIO app:
```
python3 eledmg_checker.py
```

# Sources

- Federal Office of Meteorology and Climatology MeteoSwiss
- Federal Office of Topography swisstopo
