from pywebio import *
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pyecharts.components import Table
import haversine as hs
import sqlite3
import arrow

# Custom config
config(title="Wind Speed Checker (PROTOTYPE)",
      description="Evaluate wind speeds against regulatory guidelines.")

# --- FUNCTIONS --- #

# Validate input form
def check_form_case_data(data):
    db_origin_date = arrow.get("2022-08-25") # Start of eledmg-db
    db_refresh_date = arrow.utcnow().shift(days=-1) # Refresh according to cron job
    db_limit_date = arrow.utcnow().shift(years=-2) # Older data gets deleted
    try: 
        start = arrow.get(data["damage_date_start"], "DD.MM.YYYY")
        end = arrow.get(data["damage_date_end"], "DD.MM.YYYY")
    except:
        return output.put_error(
                "ERROR: Invalid date.",
                closable=True,
                scope="scope_input_instructions")
    if start > end:
        output.put_error(
            "ERROR: End date cannot be older than start date.",
            closable=True,
            scope="scope_input_instructions")
        return ("","")
    if end.shift(weeks=-2) > start:
        output.put_error("ERROR: Max. time scope is two weeks.",
            closable=True,
            scope="scope_input_instructions")
        return ("","")
    if (start < db_origin_date) or (end < db_origin_date):
        output.put_error("ERROR: No data available for this date. Start data aggregation:" + str(db_origin_date.humanize()),
            closable=True,
            scope="scope_input_instructions")
        return ("","")
    if start > db_refresh_date or (end > db_refresh_date):
        output.put_error("ERROR: " + str(db_refresh_date.format("DD.MM.YYYY")),
            closable=True,
            scope="scope_input_instructions")
        return ("","")
    if start < db_limit_date:
        output.put_error("ERROR: Data gets deleted after two years. Earliest possible request date:" + str(db_limit_date.humanize()),
            closable=True,
            scope="scope_input_instructions")
        return ("","")

# Function to flatten tuples returned by sql queries
def flatten(lst):
    output_lst = []
    for item in lst:
        output_lst.extend(item)
    return output_lst

# --- MAIN FNCTION --- #
def main():

    # --- SESSION CONTROL --- #
    # Some layout tweaks
    session.set_env(input_panel_fixed=False,
                    output_animation=False)

    # --- INPUT --- #

    # Info block
    with output.use_scope("scope_title"):
        output.put_markdown("""# Wind Speed Checker (PROTOTYPE)""").style('margin-top: 20px')
        output.put_markdown("""Latest Update Wind Data: """ + str(arrow.utcnow().format("DD.MM.YYYY"))) # Adjust to cron job

    # User Input: Case data
    case_data = input.input_group("", [
        input.input(
                "Startdatum (DD.MM.YYYY)",
            name="damage_date_start",
            type=input.TEXT,
            required=True,
            pattern="[0-9]{2}\.[0-9]{2}\.(19|20)\d{2}$",
            maxlength="10",
            minlength="10",
            placeholder="DD.MM.YYYY"),
        input.input(
                "Enddatum (DD.MM.YYYY)",
            name="damage_date_end",
            type=input.TEXT,
            required=True,
            pattern="[0-9]{2}\.[0-9]{2}\.(19|20)\d{2}$",
            maxlength="10",
            minlength="10",
            placeholder="DD.MM.YYYY"),
        input.input(
                "PLZ",
            name="plz",
            type=input.TEXT,
            required=True,
            pattern="[0-9]{4}",
            maxlength="4",
            minlength="4",
            placeholder="PLZ"),
    ], validate = check_form_case_data)
    damage_date_start = arrow.get(case_data["damage_date_start"], "DD.MM.YYYY")
    damage_date_end = arrow.get(case_data["damage_date_end"], "DD.MM.YYYY")
    plz = case_data["plz"]

    # Define db
    db = "ch_ws_db.sqlite"

    # Connect to db
    cnx = sqlite3.connect(db)
    cur = cnx.cursor()

    # Select town names from db, returns list of tuples
    cur.execute("""SELECT Ortschaftsname FROM towns WHERE plz = ?""", (plz,))
    towns_lst = cur.fetchall()

    # Flatten list of tuples
    towns_lst = flatten(towns_lst)

    # Require specification by user if more than one town is returned
    # Else proceed with single town
    if len(towns_lst) > 1:
        town = input.select("Stadt",
            options=towns_lst,
            required=True)
    else:
        town = towns_lst[0]

    # Select coordinates for town from db
    cur.execute("""SELECT e, n, Höhe FROM towns WHERE Ortschaftsname = ? AND plz = ?""", (town, plz))
    coords_lst = cur.fetchall()

    # Convert tuples to lst
    coords_lst = flatten(coords_lst)

    # Populate dct with case data
    case_dct = {}
    case_dct["damage_date_start"] = damage_date_start
    case_dct["damage_date_end"] = damage_date_end
    case_dct["town"] = town
    case_dct["plz"] = plz
    # Längengrad, longitute (X.)
    case_dct["longitude"] = coords_lst[0]
    # Breitengrad, latitude (XX.)
    case_dct["latitude"] = coords_lst[1]
    # Elevation
    case_dct["elevation_town"] = coords_lst[2]

    # Get data from all stations
    cur.execute("""SELECT station, "abk.", breitengrad, längengrad, "Messhöhe m ü. M." FROM stations""")
    all_stations_lst = cur.fetchall()
    
    # Convert tuples to list
    all_stations_lst = [[*row] for row in all_stations_lst]

    # Find all stations within 10km
    # Exclude stations with elevation difference of more than 200m
    relevant_stations_lst = []
    excluded_stations_lst = []
    # Set radius
    radius = 10
    for station in all_stations_lst:
        coords_1 = (station[2], station[3])
        coords_2 = (case_dct["latitude"], case_dct["longitude"])
        elevation_station = station[4]
        distance = round(hs.haversine(coords_1, coords_2), 1)
        ele_diff = abs(case_dct["elevation_town"] - elevation_station)
        # Station fulfills criteria
        if (distance <= radius) and (ele_diff <= 200):
            # Store distance and elevation within station data
            station.append(distance)
            station.append(ele_diff)
            # Append station data to the relevant stations
            relevant_stations_lst.append(station)
        # Elevation difference too high
        elif (distance <= radius) and (ele_diff > 200):
            # Store distance and elevation within station data
            station.append(distance)
            station.append(ele_diff)
            # Append station data to the excluded stations
            relevant_stations_lst.append(station) # Could be moved to a different list if needed
        else:
            continue

    # Exit request if no relevant station can be found
    if len(relevant_stations_lst) == 0:
        output.clear_scope("scope_input_instructions")
        output.put_markdown("""Keine relevanten Messstationen gefunden (10km-Radius) --> Bitte starte eine Abfrage mit einer anderen PLZ.""")
        exit()

    # Get amount of relevant stations for layout adjustement
    n_stations = len(relevant_stations_lst)

    # Query relevant stations for weather data
    meteo_data_lst = []
    # Gather 10min intervall
    for station in (relevant_stations_lst + excluded_stations_lst):
        # Query db by station abreviation
        db_table_name_10min = str(station[1]) + "_wind_10min"
        db_table_name_1s = str(station[1]) + "_wind_1s"
        # Reformat dates
        db_start_dt = str(damage_date_start.format("YYYY-MM-DD"))
        db_end_dt = str(damage_date_end.format("YYYY-MM-DD"))
        # Query tables for relevant data
        cur.execute("""SELECT station, messdatum, "Wind km/h", '10min Intervall' FROM {} WHERE date(Messdatum) BETWEEN (?) AND (?)""".format(db_table_name_10min), (db_start_dt, db_end_dt,))
        data_10min = cur.fetchall()
        cur.execute("""SELECT station, messdatum, "Böen km/h", 'Böenspitzen' FROM {} WHERE date(Messdatum) BETWEEN (?) AND (?)""".format(db_table_name_1s), (db_start_dt, db_end_dt,))
        data_1s = cur.fetchall()
        data_complete = data_10min + data_1s
        # Refine data, add to list
        for row in data_complete:
            row = [*row]
            meteo_data_lst.append(row)

        # Find highest values, add to station data
        cur.execute("""SELECT MAX("Wind km/h") FROM {} WHERE date(Messdatum) BETWEEN (?) AND (?)""".format(db_table_name_10min), (db_start_dt, db_end_dt,))
        max_10min = cur.fetchall()
        station.append(max_10min[0][0])
        cur.execute("""SELECT MAX("Böen km/h") FROM {} WHERE date(Messdatum) BETWEEN (?) AND (?)""".format(db_table_name_1s), (db_start_dt, db_end_dt,))
        max_1s = cur.fetchall()
        station.append(max_1s[0][0])

    # Close db connection
    # Make sure db is updated manually or via cron
    cnx.close()

    # --- OUTPUT VISUALIZATION - GATHER DATA --- #

    # Set DataFrame headers
    df_headers = ["station",
            "abr",
            "latitude",
            "longitute",
            "elevation",
            "distance",
            "ele_diff",
            "max_10min",
            "max_1s"]

    # Populate list for DataFrame
    df_station_lst = []
    for station in relevant_stations_lst:
        df_station_lst.append(pd.DataFrame(
        data=[[
            station[0], # Station
            station[1], # Abreviation
            station[2], # Breitengrad, latitude (XX.)
            station[3], # Längengrad, longitute (X.)
            station[4], # Altitude
            station[5], # Distance to town
            station[6], # Elevation difference
            station[7], # Max 10min
            station[8], # Max 1s
            ]],
        columns=df_headers))

    # Build DataFrame from list
    df_stations = pd.concat(df_station_lst, ignore_index=True, sort=False)

    # Find highest and closest values within DataFrame
    highest_val_10min = df_stations["max_10min"].max()
    highest_val_1s = df_stations["max_1s"].max()
    closest_val_10min = df_stations.nsmallest(1, "distance")["max_10min"].values[0]
    closest_val_1s = df_stations.nsmallest(1, "distance")["max_1s"].values[0]

    # Build table (displayed in output)
    tbl = Table()
    tbl_rows = []
    for lst in relevant_stations_lst:
        tbl_lst = []
        tbl_lst.append(str(lst[0]))
        tbl_lst.append(str(lst[5]) + " km")
        tbl_lst.append(str(lst[4]) + " m")
        tbl_lst.append(str(lst[6]) + " m")
        tbl_lst.append(str(lst[7]) + " km/h")
        tbl_lst.append(str(lst[8]) + " km/h")
        tbl_rows.append(tbl_lst)

    # Sort by distance
    tbl_rows = sorted(tbl_rows, key=lambda x: x[1])

    # Add table headers
    tbl_headers = ["Station", "Δ Distance", "Altitude", "Δ Elevation", "Max. 10m", "Max. 1s"]
    tbl.add(tbl_headers, tbl_rows)

    # Case evaluation
    if (highest_val_10min < 63) and (highest_val_1s < 100):
        wide_radius = "No"
        close_radius = "No"
        verdict = "Wind speed not sufficient"
        reason = "Criteria within 10-km not met"
    elif ((highest_val_10min > 63) and (closest_val_10min < 63)) and ((highest_val_1s > 100) and (closest_val_1s < 100)):
        wide_radius = "Yes"
        close_radius = "No"
        verdict = "Wind speed not sufficient"
        reason = "Criteria within 5-km not met"
    else:
        wide_radius = "Yes"
        close_radius = "Yes"
        verdict = "Wind speed sufficient"
        reason = "Criteria met"

    # Populate list for DataFrame
    df_meteo_lst = []
    for lst in meteo_data_lst:
        df_meteo_lst.append(pd.DataFrame(
        data=[[
            lst[0],
            arrow.get(lst[1]).datetime,
            lst[2],
            lst[3],]],
        columns=["Station", "Messdatum", "km/h", "type"]))

    # Build dataframe from list
    df_meteo = pd.concat(df_meteo_lst, ignore_index=True, sort=False)

    # Remove duplicate rows
    df_meteo.drop_duplicates(subset=["Station", "Messdatum", "type"], keep="first", inplace=True)

    # Style layout
    fig = px.line(
        df_meteo,
        x="Messdatum",
        y="km/h",
        color="type",
        facet_col="Station",
        markers=True,
        facet_col_wrap=1,
        facet_row_spacing=0.07,
         color_discrete_sequence=["#000075", "#911eb4"],
        # Dynamically adjust height (not exact)
        height=400 + (n_stations * 200))

    # Update layout
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1])) # Titles
    fig.for_each_yaxis(lambda yaxis: yaxis.update(showticklabels=True)) # Tick labels Y
    fig.for_each_xaxis(lambda xaxis: xaxis.update(showticklabels=True)) # Tick labes X
    fig['layout'].update(margin=dict(l=0,r=0,b=20,t=20)) # Margin
    fig.add_hline(y=63, line_width=2, line_dash="dash", line_color="#000075", annotation_text="63 km/h") # 63 km/h dotted line
    fig.add_hline(y=100, line_width=2, line_dash="dash", line_color="#911eb4", annotation_text="100 km/h") # 100 km/h dotted line

    # --- OUTPUT VISUALIZATION - GATHER DATA --- #

    with output.use_scope("scope_visualization"):

        output.put_markdown("""
        ## Evaluation
        """).style('margin-top: 20px'),
        output.put_markdown("""
        ### Region
        """).style('margin-top: 20px')
        output.put_row([
                output.put_markdown("""Above threshold for region:"""),
                output.put_markdown("**" + str(wide_radius) + "**"),
            ], size="50% auto auto")
        output.put_row([
                output.put_markdown("Max. 10min:"),
                output.put_markdown("**" + str(highest_val_10min) + " km/h**"),
            ], size="50% auto auto")
        output.put_row([
            output.put_markdown("""Max. 1s:"""),
            output.put_markdown("**" + str(highest_val_1s) + " km/h**"),
            ], size="50% auto auto")
        output.put_markdown("""
        ### Town
        """).style('margin-top: 20px')
        output.put_row([
                output.put_markdown("""Above threshold for town:"""),
                output.put_markdown("**" + str(close_radius) + "**"),
            ], size="50% auto auto")
        output.put_row([
            output.put_markdown("""Closest Max. 10min:"""),
            output.put_markdown("**" + str(closest_val_10min) + " km/h**"),
            ], size="50% auto auto")
        output.put_row([
            output.put_markdown("""Closest Max. 1s:"""),
            output.put_markdown("**" + str(closest_val_1s) + " km/h**"),
            ], size="50% auto auto")
        output.put_markdown("""
        ### Result
        """).style('margin-top: 20px')
        output.put_row([
            output.put_markdown("""Result:"""),
            output.put_markdown("**" + str(verdict) + "**"),
            ], size="50% auto auto")
        output.put_row([
            output.put_markdown("""Reason:"""),
            output.put_markdown("**" + str(reason) + "**"),
            ], size="50% auto auto").style('margin-bottom: 40px')

        output.put_markdown("""
        ## Data
        """).style('margin-top: 20px'),

        # Plotly output to PyWebIO
        output.put_markdown("""
        ### Measurements
        """).style('margin-top: 20px'),

        output.put_html(tbl.render_notebook()).style('margin-top: 40px')

        output.put_markdown("""
        ### Visualization
        """).style('margin-top: 20px'),

        plotly_html_1 = fig.to_html(include_plotlyjs="require", full_html=False, config=config)
        output.put_html(plotly_html_1).style('margin-top: 40px')

# --- DEPLOYMENT --- #
if __name__ == '__main__':
    start_server(main, port=40523, host="0.0.0.0", debug=False)
