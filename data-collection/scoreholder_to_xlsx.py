# Scoreholder to XLSX
# Version 3
# Myles Glass - 2025

# This script streamlines getting gymnastics results data from scoreholder.com event pages.
# It has 3 main steps:
#   - getting the .json file from scoreholder.com
#   - parsing the json into pandas tables
#   - using openpyxls to create an Excel spreadsheet with the correct formatting for distribution

from ast import Name
import json
import re
import pandas as pd
import os
from openpyxl.utils import get_column_letter, column_index_from_string
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import cloudscraper 
import argparse
from gooey import Gooey, GooeyParser # Import Gooey components

verbose = 0

# Data Import
# -----------

def find_json_from_url(url):

    #create api-call url
    event_id = url.split('/')[-1] # get event id from url
    api_url = f"https://scoreholder.com/api/events/{event_id}?scope=PUBLIC"
    
    api_url = f"https://scoreholder.com/api/events/{event_id}?scope=PUBLIC"
    print(f"Calling Scoreholder API with cloudscraper: {api_url}")

    # cloudscraper instance
    scraper = cloudscraper.create_scraper(
        browser={ # You can try to mimic your browser
            'browser': 'chrome',
            'platform': 'windows', # or 'darwin' for macOS, 'linux'
            'mobile': False
        }
    )

    response_text_for_debugging = ""

    try:
        # Use scraper.get() instead of requests.get()
        # cloudscraper handles its own headers for challenges,
        # but you can still pass additional ones if needed.
        # For the first attempt, let cloudscraper do its thing.
        response = scraper.get(api_url, timeout=30) # Increased timeout as challenges can take time
        response_text_for_debugging = response.text

        print(f"API Response Status Code: {response.status_code}")
        response.raise_for_status()

        if response.status_code == 204:
            print("API returned status 204 No Content. Cannot parse JSON.")
            return None
        if not response.text.strip():
            print("API response text is empty or whitespace. Cannot parse JSON.")
            return None

        api_data = response.json()
        print("Successfully decoded JSON from Scoreholder API (via cloudscraper).")
        return api_data

    except requests.exceptions.HTTPError as http_err: # cloudscraper uses requests exceptions
        print(f"HTTP error occurred with API call: {http_err} from {api_url}")
        if http_err.response is not None:
            print(f"    Response Status Code: {http_err.response.status_code}")
            print(f"    Response Text: {http_err.response.text[:500]}")
    except requests.exceptions.Timeout:
        print(f"Request to API {api_url} timed out.")
    except requests.exceptions.RequestException as req_err:
        print(f"Error during API request to {api_url}: {req_err}")
    except json.JSONDecodeError as json_err:
        print(f"JSON decoding error from API response {api_url}: {json_err}")
        print(f"    Content that failed to decode (first 500 chars): {response_text_for_debugging[:500]}")
    except Exception as e: # Catch other potential cloudscraper-specific errors
        print(f"An unexpected error occurred with cloudscraper: {e}")
        print(f"    Content that may have caused it (first 500 chars): {response_text_for_debugging[:500]}")

    return None

# Data Parse
# ----------
# headers for data export
wag_header = ["gnz-id", "name", "club", "step", "division", "competition", "round-type", "day", "v-total", "v-d", "v-e", "v-n", "v-rank", "ub-total", "ub-d",
              "ub-e", "ub-n", "ub-rank", "bb-total", "bb-d", "bb-e", "bb-n", "bb-rank", "fx-total", "fx-d", "fx-e", "fx-n", "fx-rank", "aa-score", "aa-rank", "comp-start-date"]
mag_header = ["gnz-id", "name", "club", "step", "division", "competition", "round-type", "fx-total", "fx-d", "fx-e", "fx-n", "fx-rank", "ph-total", "ph-d", "ph-e", "ph-n", "ph-rank", "sr-total", "sr-d",
              "sr-e", "sr-n", "sr-rank", "vt-total", "vt-d", "vt-e", "vt-n", "vt-rank", "pb-total", "pb-d", "pb-e", "pb-n", "pb-rank", "hb-total", "hb-d", "hb-e", "hb-n", "hb-rank", "aa-score", "aa-rank", "comp-start-date"]

# Remove 'GS' from some GNZ-IDs
def fixId(id):
    if id.startswith("GS"):
        return id[2:]
    elif id == "":
        return "000000"
    return id

# Get the club of the gymnast
def getClub(clubs, club_id):
    for club in clubs:
        if club_id == club['club_id']:
            return club['name']

    raise NameError("Couldn't find", club_id, "in club list.")

# Get the Level/STEP of the round, with some cheeky handling of Internationals
def getLevel(tags):
    for tag in tags:
        outliers = [
            'international',
            'open',
            'u16',
            'ji',
            'si',
            'sen int',
            'jun int',
            'under 17',
            'senior open',
            'junior open',
            'junior int',
            'senior int',
            'u17',
            'u18',
            'under 18',
            'under17',
            'under18',
            'senior',
            'junior',
            'jnr int',
            'snr int'
        ]

        try:
            if tag.lower() in outliers:
                return tag
            if 'step' in tag.lower() or 'level' in tag.lower():
                try:
                    return re.findall(r'\d+', tag)[0]
                except IndexError:
                    print("TAG ERROR ______________________")
                    print(tag)
                    return "UNKNOWN"
            # hack af
            # if tag == "1" or tag == "2" or tag == "3" or tag == "4" or tag == "5" or tag == "6" or tag == "7" or tag == "8" or tag == "9" or tag == "10":
            #    return re.findall(r'\d+', tag)[0]
            # if "WAG" in tag or "MAG" in tag:
            # return re.findall(r'\d+', tag)[0]
        except NameError:
            print("TAG ERROR ______________________")
            print(tag)
            return "UNKNOWN"

# Is it a MAG or WAG Round?
def getDiscipline(tags):
    for tag in tags:
        if 'wag' in tag.lower() or 'step' in tag.lower():
            return 'WAG'
        elif 'mag' in tag.lower() or 'level' in tag.lower():
            return 'MAG'
    return 'None'

# Gets OVER/UNDER division for STEPs programme
def getDivision(tags):
    for tag in tags:
        if 'under' in tag.lower() or tag == "U":
            return 'UNDER'
        elif 'over' in tag.lower() or tag == "O":
            return 'OVER'
    return "NONE"

# Get the placing? 
def getPlacing(app_results, code):
    for result in app_results:
        if result['code'] == code:
            # check if rank exists cause sometimes they don't *shrug*
            if len(result['ranks']) != 0:
                if result['ranks'][0] != {}:
                    return result['ranks'][0]['rank']
            else:
                return 0

# Truncates/pads a float f to n decimal places without rounding
def truncate(f, n):
    '''Truncates/pads a float f to n decimal places without rounding'''
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return '.'.join([i, (d+'0'*n)[:n]])

# Format an individual apparatus score into a specific format [final_score, dv, e, nd, app_placing]
def formatScore(latest_score, placing):
    try:
        if latest_score.get('neutralDeductions') is not None:
            return [latest_score['finalScore'], latest_score['difficultyScore'], latest_score['executionScore'], latest_score['neutralDeductions'], placing]
        else:
            return [latest_score['finalScore'], latest_score['difficultyScore'], latest_score['executionScore'], 0, placing]
    except KeyError:
        print("KeyError in Formatting Score:", latest_score)
        return [0,0,0,0,0]

# Is the round defined as an All Around competition (i.e. senior apparatus finals would not be)
def isAllAround(round_type):
    aa_names = [
        "AA",
        "All Around",
        "All-Around"
    ]

    for name in aa_names:
        if name.lower() in round_type.lower():
            return True
        
    return False

# Currently, we do not want to parse any GFA or EXCEL results
def notGFA(category):
    naughty_words = [
        'Bronze', 'Silver', 'Emerald', 'Gold', 'Grade', 'Iron', 'Ruby'
    ]

    for word in naughty_words:
        if word.lower() in category.lower():
            return False
        
    return True

# Get All Clubs - get each club listed in the event file and return as a list
def getAllClubs(data):
    clubs = []
    for club in data['organizations']:
        org = {
            "club_id": club['_id'],
            "name": club['name']
        }
        if(verbose): print(org['name'], "added to clubs list")
        clubs.append(org)
    return clubs

# Return a list of all gymnasts who are listed within the event data
def getAllGymnasts(data, clubs):
    gymnasts = []
    for competitor in data['competitors']:

        try:
            gnz_id = fixId(competitor['number'])
        except KeyError:
            gnz_id = ""

        if len(competitor['tags']) != 0:
            gymnast = {
                "sh_id": competitor['_id'],
                "gnzid": gnz_id,
                "name": competitor['name'],
                "club": getClub(clubs, competitor['organization']),
                "level/step": getLevel(competitor['tags']),
                "discipline": getDiscipline(competitor['tags']),
                "division": getDivision(competitor['tags'])
            }
        else:
            gymnast = {
                "sh_id": competitor['_id'],
                "gnzid": gnz_id,
                "name": competitor['name'],
                "club": getClub(clubs, competitor['organization']),
                "level/step": 'NONE',
                "discipline": 'NONE',
                "division": 'NONE'
            }

        if verbose:
            print(gymnast['name'], gymnast['level/step'],
                    gymnast['division'], "added to gymnast list")
        gymnasts.append(gymnast)
    return gymnasts

# creates a dataframe of the specified round, and returns it as a list [name, dataframe]
def create_round_dataframe(data, round, clubs, gymnasts, competition_name):
    # check if GFA
    if notGFA(round['category']):
        rows = []
        round_name = round['name']
        discipline = round['discipline']
        if(verbose): print("Creating table for", discipline, round_name, round['category'])

        for competitor in round['competitors']:
            current_gymnast = ''
            # get gymnast data
            for gymnast in gymnasts:
                if gymnast['sh_id'] == competitor['id']:
                    current_gymnast = gymnast

            score_ids = competitor['results']['scores']
            app_results = competitor['results']['apparatus']

            # create arrays to fill for each apparatus
            # pattern: total - difficulty - execution - penalty - rank
            vt_score = [0, 0, 0, 0, 0]
            ub_score = [0, 0, 0, 0, 0]
            bb_score = [0, 0, 0, 0, 0]
            fx_score = [0, 0, 0, 0, 0]
            ph_score = [0, 0, 0, 0, 0]
            sr_score = [0, 0, 0, 0, 0]
            pb_score = [0, 0, 0, 0, 0]
            hb_score = [0, 0, 0, 0, 0]
            timestamp = None

            # Check if gymnasts are doing more than one vault
            two_vaults = False
            vault_count = 0
            vault_flag = False
            
            for id in score_ids:
                for score in data['scores']:
                    if id == score['_id']:
                        if score['apparatus'] == "VT":
                            if vault_flag:
                                two_vaults = True
                            vault_flag = True

            # Get Scores and Build Row
            for score_id in score_ids:
                for score in data['scores']:
                    if score_id == score['_id']:
                        # we're going to assume from a little bit of poking that scores attached to gymnast in round are the most recent revision
                        latest_score = score['history'][len(
                            score['history']) - 1]

                        timestamp = latest_score['timestamp']
                        if latest_score['type'] == 'NORMAL':

                            match score['apparatus']:
                                case 'VT':
                                    if two_vaults and vault_count == 1:
                                        avg_total = float(truncate((vt_score[0] + latest_score['finalScore']) / 2, 3))
                                        avg_diff = "{:.1f}".format((vt_score[1] + latest_score['difficultyScore']) / 2)
                                        avg_e = float(truncate((vt_score[2] + latest_score['executionScore']) / 2, 3))

                                        # if this score has a neutral deduction
                                        if latest_score.get('neutralDeductions') is not None :
                                            # if the other one doesn't...
                                            if vt_score[3] == 0:
                                                vt_score = [avg_total, avg_diff, avg_e, "{:.2f}".format(latest_score['neutralDeductions'] / 2), getPlacing(app_results, 'VT')]
                                            #if they both got them
                                            else:
                                                vt_score = [avg_total, avg_diff, avg_e, "{:.2f}".format((vt_score[3] + latest_score['neutralDeductions']) / 2), getPlacing(app_results, 'VT')]
                                        # or if the last one does but not the first
                                        elif vt_score[3] > 0:
                                            vt_score = [avg_total, avg_diff, avg_e, "{:.2f}".format(vt_score[3] / 2), getPlacing(app_results, 'VT')]
                                        else:
                                            vt_score = [avg_total, avg_diff, avg_e, 0, getPlacing(
                                                app_results, 'VT')]

                                    elif two_vaults and vault_count == 0:
                                        vt_score = formatScore(
                                            latest_score, getPlacing(app_results, 'VT'))
                                        vault_count += 1

                                    else:
                                        vt_score = formatScore(
                                            latest_score, getPlacing(app_results, 'VT'))
                                case 'FX':
                                    fx_score = formatScore(
                                        latest_score, getPlacing(app_results, 'FX'))
                                case 'UB':
                                    ub_score = formatScore(
                                        latest_score, getPlacing(app_results, 'UB'))
                                case 'BB':
                                    bb_score = formatScore(
                                        latest_score, getPlacing(app_results, 'BB'))
                                case 'PH':
                                    ph_score = formatScore(
                                        latest_score, getPlacing(app_results, 'PH'))
                                case 'SR':
                                    sr_score = formatScore(
                                        latest_score, getPlacing(app_results, 'SR'))
                                case 'PB':
                                    pb_score = formatScore(
                                        latest_score, getPlacing(app_results, 'PB'))
                                case 'HB':
                                    hb_score = formatScore(
                                        latest_score, getPlacing(app_results, 'HB'))
                                
            # Get the All Around placing if it exists
            aa_placing = 0
            if isAllAround(round_name):
                try:
                    aa_placing = competitor['results']['allAround']['ranks'][0]['rank']
                except KeyError:
                    if(verbose): print('KeyError getting AA Placing', competitor['results']['allAround']['ranks'])
                    aa_placing = 0
                except IndexError:
                    if(verbose): print('IndexError getting AA Placing', competitor['results']['allAround']['ranks'])
                    aa_placing = 0

            # Calculate All Around score and score row
            if discipline == 'WAG':
                aa_score = "{:.3f}".format(vt_score[0] + ub_score[0] + bb_score[0] + fx_score[0])
                row = [current_gymnast['gnzid'], current_gymnast['name'], current_gymnast['club'], round['category'], current_gymnast['division'], competition_name, round_name, "", vt_score[0], vt_score[1], vt_score[2], vt_score[3], vt_score[4], ub_score[0], ub_score[1], ub_score[2], ub_score[3], ub_score[4], bb_score[0], bb_score[1], bb_score[2], bb_score[3], bb_score[4], fx_score[0], fx_score[1], fx_score[2], fx_score[3], fx_score[4], aa_score, aa_placing, data['event']['startDate']]
            if discipline == 'MAG':
                aa_score = "{:.3f}".format(fx_score[0] + ph_score[0] + sr_score[0] + vt_score[0] + pb_score[0] + hb_score[0])
                row = [current_gymnast['gnzid'], current_gymnast['name'], current_gymnast['club'], round['category'], current_gymnast['division'], competition_name, round_name, fx_score[0], fx_score[1], fx_score[2], fx_score[3], fx_score[4], ph_score[0], ph_score[1], ph_score[2], ph_score[3], ph_score[4], sr_score[0], sr_score[1], sr_score[2], sr_score[3], sr_score[4], vt_score[0], vt_score[1], vt_score[2], vt_score[3], vt_score[4], pb_score[0], pb_score[1], pb_score[2], pb_score[3], pb_score[4], hb_score[0], hb_score[1], hb_score[2], hb_score[3], hb_score[4], aa_score, aa_placing, data['event']['startDate']]

            rows.append(row)

        df = pd.DataFrame(rows)
        filename = (discipline + "\\" + competition_name + "\\" + competition_name + " - " + discipline + \
            " " + round['category'] + " " + round_name).replace(':', '').replace('/', '+')
        
        if(verbose): print(f"created dataframe for {filename}")

        return [filename, df]

# Excel Output
# ------------
def sanitize_sheet_name(filename):
    """
    Sanitizes a filename to be a valid Excel sheet name.
    Excel sheet names must be 31 characters or less and cannot contain:
    * (asterisk)
    ? (question mark)
    : (colon)
    / (forward slash)
    \\ (backslash)
    [ (left square bracket)
    ] (right square bracket)
    """
    # Remove any file extension
    name_without_extension = os.path.splitext(filename)[0]
    # Replace invalid characters with an underscore
    sanitized_name = re.sub(r'[\\/*?:\[\]]', '_', name_without_extension).rsplit(' - ', 1)[-1]
    if(verbose): print(f"Sheet Name sanitised to {sanitized_name[:31]}")
    
    # Truncate to 31 characters if necessary
    return sanitized_name[:31]

def set_col_decimal_place(df, worksheet, decimal_format_column_letter, decimal_format_string):
    try:
        # Ensure decimal_format_column_letter is valid and df has enough columns
        col_to_format_idx = column_index_from_string(decimal_format_column_letter.upper())

        if 1 <= col_to_format_idx <= df.shape[1]:
            if(verbose): print(f"   - Applying decimal format '{decimal_format_string}' to column '{decimal_format_column_letter.upper()}' in sheet")
            for row_idx in range(2, worksheet.max_row + 1): # Start from row 2 to skip header
                cell = worksheet[f"{decimal_format_column_letter.upper()}{row_idx}"]
                if isinstance(cell.value, (int, float)): # Check if it's a number
                    cell.number_format = decimal_format_string
        else:
            print(f"   - Warning: Column '{decimal_format_column_letter.upper()}' for decimal formatting is out of bounds for sheet (max cols: {df.shape[1]}).")
    except TypeError:
            print(f"   - Warning: Invalid column letter '{decimal_format_column_letter}' provided for decimal formatting.")

def set_col_width(worksheet, col, width):
    worksheet.column_dimensions[col].width = width
    if(verbose): print(f"   - Applying column with of {width} to column {col}")

def dataframes_to_xlsx (dataframes_dict, output_excel_file, directory):
    try:
        if not isinstance(dataframes_dict, dict) or not dataframes_dict:
            print("Error: Input must be a non-empty dictionary of DataFrames.")
            return
            
        full_path = os.path.join(directory, output_excel_file)

        writer = pd.ExcelWriter(output_excel_file, engine="openpyxl")
        if(verbose): print(f"Processing DataFrames for Excel output: {full_path}")
        workbook = writer.book

        for sheet_key, df in dataframes_dict.items():
            if not isinstance(df, pd.DataFrame):
                print(f"Warning: Item with key '{sheet_key}' is not a DataFrame. Skipping.")
                continue

            sheet_name = sanitize_sheet_name(str(sheet_key))
            try:
                if "WAG" in sheet_name.split(" "):
                    df.to_excel(writer, sheet_name=sheet_name, header=wag_header, index=False)
                if "MAG" in sheet_name.split(" "):    
                    df.to_excel(writer, sheet_name=sheet_name, header=mag_header, index=False)
                if(verbose): print(f"Successfully added DataFrame for key '{sheet_key}' as sheet '{sheet_name}'.")

                worksheet = writer.sheets[sheet_name]

                if not df.empty:
                    worksheet.auto_filter.ref = worksheet.dimensions
                    if(verbose): print(f"   - Applied auto-filter to sheet '{sheet_name}'.")

                    worksheet.freeze_panes = 'D2'

                    if "WAG" in sheet_name.split(" "):
                        worksheet.column_dimensions["F"].hidden = True 
                        worksheet.column_dimensions["H"].hidden = True 
                        worksheet.column_dimensions["AE"].hidden = True 
                    
                        set_col_decimal_place(df, worksheet, "I", "0.000")
                        set_col_decimal_place(df, worksheet, "K", "0.000")
                        set_col_decimal_place(df, worksheet, "N", "0.000")
                        set_col_decimal_place(df, worksheet, "P", "0.000")
                        set_col_decimal_place(df, worksheet, "S", "0.000")
                        set_col_decimal_place(df, worksheet, "U", "0.000")
                        set_col_decimal_place(df, worksheet, "X", "0.000")
                        set_col_decimal_place(df, worksheet, "Z", "0.000")
                        set_col_decimal_place(df, worksheet, "AC", "0.000")

                        set_col_decimal_place(df, worksheet, "J", "0.0")
                        set_col_decimal_place(df, worksheet, "L", "0.0")
                        set_col_decimal_place(df, worksheet, "O", "0.0")
                        set_col_decimal_place(df, worksheet, "Q", "0.0")
                        set_col_decimal_place(df, worksheet, "T", "0.0")
                        set_col_decimal_place(df, worksheet, "V", "0.0")
                        set_col_decimal_place(df, worksheet, "Y", "0.0")
                        set_col_decimal_place(df, worksheet, "AA", "0.0")

                        set_col_width(worksheet, "B", 18)
                        set_col_width(worksheet, "C", 18)
                        set_col_width(worksheet, "D", 12)
                        set_col_width(worksheet, "H", 18)
                    
                    if "MAG" in sheet_name.split(" "):
                        worksheet.column_dimensions["E"].hidden = True
                        worksheet.column_dimensions["AN"].hidden = True

                        set_col_decimal_place(df, worksheet, "H", "0.000")
                        set_col_decimal_place(df, worksheet, "J", "0.000")
                        set_col_decimal_place(df, worksheet, "M", "0.000")
                        set_col_decimal_place(df, worksheet, "O", "0.000")
                        set_col_decimal_place(df, worksheet, "T", "0.000")
                        set_col_decimal_place(df, worksheet, "W", "0.000")
                        set_col_decimal_place(df, worksheet, "Y", "0.000")
                        set_col_decimal_place(df, worksheet, "AB", "0.000")
                        set_col_decimal_place(df, worksheet, "AD", "0.000")
                        set_col_decimal_place(df, worksheet, "AG", "0.000")
                        set_col_decimal_place(df, worksheet, "AI", "0.000")
                        set_col_decimal_place(df, worksheet, "AL", "0.000")

                        set_col_decimal_place(df, worksheet, "I", "0.0")
                        set_col_decimal_place(df, worksheet, "K", "0.0")
                        set_col_decimal_place(df, worksheet, "N", "0.0")
                        set_col_decimal_place(df, worksheet, "P", "0.0")
                        set_col_decimal_place(df, worksheet, "S", "0.0")
                        set_col_decimal_place(df, worksheet, "U", "0.0")
                        set_col_decimal_place(df, worksheet, "X", "0.0")
                        set_col_decimal_place(df, worksheet, "Z", "0.0")
                        set_col_decimal_place(df, worksheet, "AC", "0.0")
                        set_col_decimal_place(df, worksheet, "AE", "0.0")
                        set_col_decimal_place(df, worksheet, "AH", "0.0")
                        set_col_decimal_place(df, worksheet, "AJ", "0.0")

                        set_col_width(worksheet, "B", 18)
                        set_col_width(worksheet, "C", 18)
                        set_col_width(worksheet, "F", 12)

            except Exception as e: # Catch errors specific to processing one DataFrame
                print(f"Error processing DataFrame for key '{sheet_key}' (sheet '{sheet_name}'): {e}")

            # Save the Excel file
        try:
            writer.close() # Prior to pandas 1.3.0, use writer.save()
            print(f"\nExcel file '{output_excel_file}' created successfully!")
        except Exception as e: # For pandas < 1.3.0, writer.save() might be needed.
            print(f"Error saving Excel file: {e}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

@Gooey(program_name="URL Processor GUI",
       program_description="Enter a URL to process and specify an output file.",
       default_size=(600, 400)) # Optional: set default window size
def main():
    # Use GooeyParser instead of argparse.ArgumentParser
    parser = GooeyParser(description="Processes a URL and saves its content to a file.")

    # 1. URL (Positional Argument - required)
    #    'url' is the name of the argument.
    #    help is the description that Gooey (and --help) will show.
    parser.add_argument(
        'url',  # Name of the argument (will be args.url)
        help="The URL you want to process",
        widget="TextField"
    )

    parser.add_argument(
        'directory', # Changed from --output
        help="Directory where the output file will be saved",
        widget="DirChooser", # Gooey specific: provides a directory chooser dialog
        gooey_options={
            'message': "Choose the output directory",
            'default_path': '.' # Start in the current directory or last used
        }
    )

    args = parser.parse_args()

    print("Scoreholder to XLSX Converter")
    print("----------------------")
    print("This will scrape data from a Scoreholder event page, convert the .json data into tables, and then save each round as a sheet within an .xlsx spreadsheet")
    print("Warning! Scoreholder can change it's backend at any time, and this may render this script useless. There is also a non-zero chance that results aren't accurate, due to numerous factors. Please be careful and do some checks to ensure data is accurate")

    # import data from scoreholder
    #scoreholder_url = input("Please enter the Scoreholder url: ")
    #test_url = "https://scoreholder.com/events/68292449e05232619d6967a9"
    # test_url = "https://d2w3vmub0iheo.cloudfront.net/event-archives/68292449e05232619d6967a9-4428.json"
    #if not scoreholder_url:
    #    scoreholder_url = test_url
    data = find_json_from_url(args.url)

    # parse information from data and create dataframes
    competition_year = data['event']['startDate'][:4]   # competition year (XXXX)
    competition_name = data['event']['name']            # competition name
    if(competition_year not in competition_name):       # ensure year is in competition name, to ensure data doesn't get muddled in future years
        competition_name += " " + competition_year
    print('Creating results tables for', competition_name, '...')
    clubs = getAllClubs(data)
    gymnasts = getAllGymnasts(data, clubs)
    roundDataframes = {}
    for round in data['rounds']:
        newRound = create_round_dataframe(data, round, clubs, gymnasts, competition_name)
        roundDataframes[newRound[0]] = newRound[1]
        if(verbose): print(f"Added '{newRound[0]} to rounds.'")

    # output to excel
    output_name = competition_name + '.xlsx'
    dataframes_to_xlsx(roundDataframes, output_name, args.directory)

    print("End")
    

if __name__ == "__main__":
    main()