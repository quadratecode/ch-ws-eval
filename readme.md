# About

A simple web app to request wind speeds from the database residing in [this repo](https://github.com/quadratecode/eledmg-db) and evaluate them against regulatory guidelines. Made with [PyWebIO](https://github.com/pywebio/PyWebIO).

# Disclaimer

This is a prototype, results are inaccurate and should not be relied upon. NOT FOR PRODUCTION USE.

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
python3 speed_eval.py
```

# Sources

- Federal Office of Meteorology and Climatology MeteoSwiss
- Federal Office of Topography swisstopo
