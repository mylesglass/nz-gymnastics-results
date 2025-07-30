import json
import os
import re
import pandas as pd
import os
from openpyxl.utils import get_column_letter, column_index_from_string

# Global Variable
VERBOSE_CONSOLE = 0;
SOURCE_DIR = "2025\\json"
OUTPUT_DIR = "2025\\xlsx"

# Remove 'GS' from some GNZ-IDs
def fixId(id):
    if id.startswith("GS"):
        return id[2:]
    elif id == "":
        return "000000"
    return id

def getPerformanceID(performanceIndividuals, participantID):
    performanceIds = []
    for individual in performanceIndividuals:
        if individual['participantId'] == participantID:
            configs = individual.get('resultTableConfigs', [])
            performanceID = {
                "id": individual['_id'],
                "unit_id": individual['unitId'],
                "result_table_configs": configs,
                "scores": []
            }
            performanceIds.append(performanceID)
        #else:
        #    print(f"ERROR: No performanceID for {participantID}")
    return performanceIds

# Get All Clubs - get each club listed in the event file and return as a list
def getAllClubs(data):
    clubs = []
    for club in data['eventOrganizations']:
        org = {
            "club_id": club['_id'],
            "name": club['name']
        }
        if VERBOSE_CONSOLE: print(org['name'], "(", org["club_id"], ") added to clubs list")
        clubs.append(org)
    return clubs

# Get a club name from an id
def getClub(clubs, club_id):
    for club in clubs:
        if club_id == club['club_id']:
            return club['name']

    raise NameError("Couldn't find", club_id, "in club list.")

# Get Unit Info for a Performance ID
def getUnitInfo(data, performanceIds):
    unitInfos = []
    for id in performanceIds:
        for unit in data['units']:
            if unit['_id'] == id['unit_id']:
                name = unit['name']
                discipline = 'UNKNOWN'
                level = 'UNKNOWN'
                
                # Discipline
                if 'wag' in name.lower() or 'step' in name.lower():
                    discipline = 'WAG'
                elif 'mag' in name.lower() or 'level' in name.lower():
                    discipline = 'MAG'


                # Level
                if 'step' in name.lower():
                    level = "STEP " + re.findall(r'\d+', name)[0]
                elif 'level' in name.lower():
                    level = "Level " + re.findall(r'\d+', name)[0]

                unitInfo = {
                    "name": name,
                    "discipline": discipline,
                    "level": level,
                }

                unitInfos.append(unitInfo)

    return unitInfos

def getDivision(data, performanceIds):
    for id in performanceIds:
        for config in id['result_table_configs']:
            if len(config) > 0:
                table_id = config['resultTableId']
                if len(data['performanceRules']) > 0:
                    for rule in data['performanceRules']:
                        for node in rule['competition']['nodeTree']['nodes']:
                            if node['id'] == table_id:
                                return node['name']

def parseDivision(name, unitInfo):
    if unitInfo['discipline'] == 'WAG':
        underTags = ['under', 'division a']
        overTags = ['over', 'division b']
        internationalTags = ['international', 'int']

        for tag in underTags:
            if tag in name.lower():
                return 'UNDER'
        for tag in overTags:
            if tag in name.lower():
                return 'OVER'
        for tag in internationalTags:
            if tag in name.lower():
                return 'INTERNATIONAL'
        if has_singular_a(name):    
            return 'UNDER'
        if has_singular_b(name):
            return 'OVER'
            
        return "OPEN"
    if unitInfo['discipline'] == 'MAG':
        return 'OPEN'

def has_singular_a(text_to_search):
  pattern = r'\bA\b'
  return bool(re.search(pattern, text_to_search))

def has_singular_b(text_to_search):
  pattern = r'\bB\b'
  return bool(re.search(pattern, text_to_search))

# Return a list of all gymnasts who are listed as participants within the participant data
def getAllGymnasts(data, clubs):
    gymnasts = []
    for participant in data['eventParticipants']:

        try:
            gnz_id = fixId(participant['identifier'])
        except KeyError:
            gnz_id = ""
        
        performanceIds = getPerformanceID(data['performanceIndividuals'], participant['_id'])
        if len(performanceIds) == 0: 
            continue

        unitInfos = getUnitInfo(data, performanceIds)

        gfa_terms = ["gfa", "novice", "iron", "bronze", "silver", "gold", "emerald", "diamond", "ruby"]

        for term in gfa_terms:
            if term in unitInfos[0]['name'].lower():
                continue

        if "novice" in unitInfos[0]['name'].lower():
            continue
        if "gfa" in unitInfos[0]['name'].lower():
            continue
        if "iron" in unitInfos[0]['name'].lower():
            continue
        if "bronze" in unitInfos[0]['name'].lower():
            continue
        if "silver" in unitInfos[0]['name'].lower():
            continue
        if "gold" in unitInfos[0]['name'].lower():
            continue
        if "emerald" in unitInfos[0]['name'].lower():
            continue
        if "diamond" in unitInfos[0]['name'].lower():
            continue
        if "ruby" in unitInfos[0]['name'].lower():
            continue

        try: 
            division = parseDivision(getDivision(data, performanceIds), unitInfos[0])
        except IndexError:
            division = "NONE"
            print(f"INDEX ERROR on unitInfos: {unitInfos}")
            print(f"performance ids: {performanceIds}")


        gymnast = {
            "participant_id": participant['_id'],
            "gnz_id": gnz_id,
            "performance_ids": performanceIds,
            "name": participant['name'],
            "club": getClub(clubs, participant['organizationId']),
            "level": unitInfos[0]['level'],
            "division": division,
            "discipline": unitInfos[0]['discipline']
        }

        if VERBOSE_CONSOLE: print(f"GNZ: {gymnast['gnz_id']} - {gymnast['name']} - {gymnast['club']} - PartID: {gymnast['participant_id']} - # of PerfID: {len(gymnast['performance_ids'])} - {gymnast['discipline']} {gymnast['level']} {gymnast['division']} has been added to gymnast list")
        gymnasts.append(gymnast)
    return gymnasts

def getUnitNameFromId(data, unit_id):
    for unit in data['units']:
        if unit['_id'] == unit_id:
            return unit['name']
        
def getDisciplineFromId(data, unit_id):
    for unit in data['units']:
        if unit['_id'] == unit_id:            
            if 'wag' in unit['name'].lower():
                return 'WAG'
            elif 'mag' in unit['name'].lower():
                return 'MAG'

def getLevelFromId(data, unit_id):
    for unit in data['units']:
        if unit['_id'] == unit_id:            
            if 'step' in unit['name'].lower():
                return "STEP " + re.findall(r'\d+', unit['name'])[0]
            elif 'level' in unit['name'].lower():
                return "Level " + re.findall(r'\d+', unit['name'])[0]
            else:
                return unit['name']
            
def getGymnastFromEntityId(gymnasts, entity_id):
    for gymnast in gymnasts:
        for performance_id in gymnast['performance_ids']:
            if performance_id['id'] == entity_id:
                return gymnast
            
def getResultTableFromId(data, result_table_id):
    for table in data['performanceResultTables']:
        if table['resultTableId'] == result_table_id:
            return table
        
def findScoreName(data, id):
    for rule in data['performanceRules']:
        if "scores" in rule:
            for score in rule['scores']:
                try:
                    # Attempt to access the nested list directly
                    outputs = score['nodeTree']['interface']['outputs']
                    
                    # Find the first item in the list that matches the id
                    for output in outputs:
                        if output.get('id') == id:
                            name = output.get('name')
                            if name:
                                return name
                except (KeyError, TypeError):
                    print(KeyError, TypeError)
                    # This block runs if any key is missing or if a value is not a dictionary/list.
                    # You can handle the error or simply pass if no action is needed.
                    return "None"
        
def getPerformanceScoreItemFromId(data, id):
    for item in data['performanceScores']:
        if item['_id'] == id:
            if "publicOutputs" in item:
                score = {}
                for key, value in item['publicOutputs'].items():
                    score[findScoreName(data, key)] = value

                return score
    
def getScoreItemFromRanking(data, ranking, gymnasts, score_name, unitId):
    for gymnast in gymnasts:
        for performance in gymnast['performance_ids']:
            if performance['id'] == ranking['entityId']:
                roundName = getUnitNameFromId(data, unitId)
                level = getLevelFromId(data, unitId)
                discipline = getDisciplineFromId(data, unitId)

                result = {}
                if "value" not in ranking:
                    result = {
                        score_name.lower() +"-execution": 0,
                        score_name.lower() +"-difficuly": 0,
                        score_name.lower() +"-neutral_deduction": 0,
                        score_name.lower() +"-rank": "DNS",
                        score_name.lower() + "-score": 0,
                        "gymnast_id": gymnast['participant_id'],
                        "round_name": roundName,
                        "discipline": discipline,
                        "level": level
                    }
                    performance['scores'].append(result)
                    return result

                if ranking['value'] == "dns" or ranking['value'] == "dnf":
                    
                    if "all-around" in score_name.lower():
                        result = {
                            score_name.lower() +"-rank": "DNS",
                            score_name.lower() + "-score": 0,
                            "gymnast_id": gymnast['participant_id'],
                            "round_name": roundName,
                            "discipline": discipline,
                            "level": level
                        }
                        performance['scores'].append(result)
                        return result
                
                    result = {
                        score_name.lower() +"-execution": 0,
                        score_name.lower() +"-difficuly": 0,
                        score_name.lower() +"-neutral_deduction": 0,
                        score_name.lower() +"-rank": "DNS",
                        score_name.lower() + "-score": 0,
                        "gymnast_id": gymnast['participant_id'],
                        "round_name": roundName,
                        "discipline": discipline,
                        "level": level
                    }
                    performance['scores'].append(result)
                    return result

                if ranking["sourceItems"][0]['itemType'] == "result-set":
                    if ranking["sourceItems"][0]['status'] == "discarded":
                        continue

                    if "rank" not in ranking:
                        temp_rank = 0
                    else:
                        temp_rank = ranking["rank"]

                    result = {
                        "all-around" + "-score": ranking['value'],
                        "all-around" +"-rank": temp_rank,
                        "gymnast_id": gymnast['participant_id'],
                        "round_name": roundName,
                        "discipline": discipline,
                        "level": level
                    }
                    performance['scores'].append(result)
                    return result

                performanceScoreItem = getPerformanceScoreItemFromId(data, ranking["sourceItems"][0]['itemId'])
                if performanceScoreItem is None: continue
                if score_name.lower() == "total": continue

                result = {
                    score_name.lower() +"-execution": performanceScoreItem['Execution'],
                    score_name.lower() +"-difficuly": performanceScoreItem['Difficulty'],
                    score_name.lower() +"-neutral_deduction": performanceScoreItem['Neutral Deductions'],
                    score_name.lower() +"-score": checkZeroScore(performanceScoreItem['Score']),
                    score_name.lower() +"-rank": ranking['rank'],
                    "gymnast_id": gymnast['participant_id'],
                    "round_name": roundName,
                    "discipline": discipline,
                    "level": level
                }

                performance['scores'].append(result)
                return result
                            
def checkZeroScore(score):
    if score == "zero":
        return 0
    return score

def getGymnastNameFromPartId(gymnasts, part_id):
    for gymnast in gymnasts:
        if gymnast['participant_id'] == part_id:
            return gymnast['name']
        
def getGymnastFromPartId(gymnasts, part_id):
    for gymnast in gymnasts:
        if gymnast['participant_id'] == part_id:
            return gymnast

def getAppScore(scores, app_type):
    for score in scores:
        for key, value in score.items():
            if app_type in key:
                return score
    return {
        app_type.lower() +"-execution": 0,
        app_type.lower() +"-difficuly": 0,
        app_type.lower() +"-neutral_deduction": 0,
        app_type.lower() +"-rank": "DNS",
        app_type.lower() + "-score": 0,
        "round_name": "ERROR"
    }
            
def set_col_width(worksheet, col, width):
    worksheet.column_dimensions[col].width = width
    if(VERBOSE_CONSOLE): print(f"   - Applying column with of {width} to column {col}")

def set_col_decimal_place(df, worksheet, decimal_format_column_letter, decimal_format_string):
    try:
        # Ensure decimal_format_column_letter is valid and df has enough columns
        col_to_format_idx = column_index_from_string(decimal_format_column_letter.upper())

        if 1 <= col_to_format_idx <= df.shape[1]:
            if(VERBOSE_CONSOLE): print(f"   - Applying decimal format '{decimal_format_string}' to column '{decimal_format_column_letter.upper()}' in sheet")
            for row_idx in range(2, worksheet.max_row + 1): # Start from row 2 to skip header
                cell = worksheet[f"{decimal_format_column_letter.upper()}{row_idx}"]
                if isinstance(cell.value, (int, float)): # Check if it's a number
                    cell.number_format = decimal_format_string
        else:
            print(f"   - Warning: Column '{decimal_format_column_letter.upper()}' for decimal formatting is out of bounds for sheet (max cols: {df.shape[1]}).")
    except TypeError:
            print(f"   - Warning: Invalid column letter '{decimal_format_column_letter}' provided for decimal formatting.")

def dataframes_to_xlsx (dataframes_dict, output_excel_file, directory):
    try:          
        full_path = os.path.join(directory, output_excel_file)

        writer = pd.ExcelWriter(output_excel_file, engine="openpyxl")
        if(VERBOSE_CONSOLE): print(f"Processing DataFrames for Excel output: {full_path}")
        workbook = writer.book

        for sheet_key, df in dataframes_dict.items():
            if not isinstance(df, pd.DataFrame):
                print(f"Warning: Item with key '{sheet_key}' is not a DataFrame. Skipping.")
                continue

            sheet_name = str(sheet_key)
            try:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                if(VERBOSE_CONSOLE): print(f"Successfully added DataFrame for key '{sheet_key}' as sheet '{sheet_name}'.")

                worksheet = writer.sheets[sheet_name]

                if not df.empty:
                    worksheet.auto_filter.ref = worksheet.dimensions
                    if(VERBOSE_CONSOLE): print(f"   - Applied auto-filter to sheet '{sheet_name}'.")

                    worksheet.freeze_panes = 'D2'

                    worksheet.column_dimensions["B"].hidden = True
                    worksheet.column_dimensions["D"].hidden = True 
                
                    set_col_decimal_place(df, worksheet, "J", "0.000")
                    set_col_decimal_place(df, worksheet, "M", "0.000")
                    set_col_decimal_place(df, worksheet, "O", "0.000")
                    set_col_decimal_place(df, worksheet, "R", "0.000")
                    set_col_decimal_place(df, worksheet, "T", "0.000")
                    set_col_decimal_place(df, worksheet, "W", "0.000")
                    set_col_decimal_place(df, worksheet, "Y", "0.000")
                    set_col_decimal_place(df, worksheet, "AB", "0.000")
                    set_col_decimal_place(df, worksheet, "AD", "0.000")

                    set_col_decimal_place(df, worksheet, "K", "0.0")
                    set_col_decimal_place(df, worksheet, "L", "0.0")
                    set_col_decimal_place(df, worksheet, "P", "0.0")
                    set_col_decimal_place(df, worksheet, "Q", "0.0")
                    set_col_decimal_place(df, worksheet, "T", "0.0")
                    set_col_decimal_place(df, worksheet, "U", "0.0")
                    set_col_decimal_place(df, worksheet, "V", "0.0")
                    set_col_decimal_place(df, worksheet, "Z", "0.0")
                    set_col_decimal_place(df, worksheet, "AA", "0.0")

                    set_col_width(worksheet, "C", 18)
                    set_col_width(worksheet, "G", 18)
                    set_col_width(worksheet, "H", 24)
                    set_col_width(worksheet, "I", 18)

                    if "MAG" in sheet_name.split(" "):
                        set_col_decimal_place(df, worksheet, "AG", "0.000")
                        set_col_decimal_place(df, worksheet, "AI", "0.000")
                        set_col_decimal_place(df, worksheet, "AL", "0.000")
                        set_col_decimal_place(df, worksheet, "AN", "0.000")

                        set_col_decimal_place(df, worksheet, "AE", "0.0")
                        set_col_decimal_place(df, worksheet, "AF", "0.0")
                        set_col_decimal_place(df, worksheet, "AJ", "0.0")
                        set_col_decimal_place(df, worksheet, "AK", "0.0")

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

def getScoreNameFromRoundName(roundName):
    if "vault" in roundName.lower():
        return "Vault"
    elif "uneven" in roundName.lower():
        return "U-Bars"
    elif "beam" in roundName.lower():
        return "Beam"
    elif "floor" in roundName.lower():
        return "Floor"
    elif "rings" in roundName.lower():
        return "Rings"
    elif "pommel" in roundName.lower():
        return "Pommel"
    elif "p-bars" in roundName.lower():
        return "P-Bars"
    elif "parallel" in roundName.lower():
        return "P-Bars"
    elif "h-bar" in roundName.lower():
        return "H-Bar"
    elif "horizontal" in roundName.lower():
        return "H-Bar"
    elif "all-around" in roundName.lower():
        return "All-Around" 
    return roundName

if __name__ == "__main__":
    print("ScoreholderJSON to XLSX Converter Script")
    print("----------------------")

    # load data
    if VERBOSE_CONSOLE: print("Loading Data...")

    wagResults = []
    magResults = []

    for file in os.listdir(SOURCE_DIR):
        if file.endswith('.json'):
            file_location = SOURCE_DIR + "\\" + file
            json_file = open(file_location)
            data = json.load(json_file)
                
            if VERBOSE_CONSOLE: print(f"Processing file {file}")

            # get competition information
            if(len(data['events']) > 1):
                print(f"Error: length of events is greater than 1")
                continue

            competition_year = data['events'][0]['startDate'][:4]   # competition year (XXXX)
            
            competition_name = data['events'][0]['name']            # competition name
            print(f"Parsing data from {competition_name}")
            if(competition_year not in competition_name):       # ensure year is in competition name, to ensure data doesn't get muddled in future years
                competition_name += " " + competition_year

            # create club and gymnast datasets for later reference
            clubs = getAllClubs(data)
            print(f"{len(clubs)} clubs created")
            gymnasts = getAllGymnasts(data, clubs)
            print(f"{len(gymnasts)} gymnasts created")
            scores = []

            score_count = 0
            for rule in data['performanceRules']:
                if "competition" in rule:
                    if "nodeTree" in rule['competition']:
                        if "nodes" in rule['competition']['nodeTree']:
                            for node in rule['competition']['nodeTree']['nodes']:
                                if "resultSets" in node:
                                    roundName = node['name'].replace('|', ' ')
                                    scores = []

                                    if "Group" in roundName: continue

                                    for ruleResultSet in node['resultSets']:
                                        score_name = ruleResultSet['name']
                                        if "total" in score_name.lower(): 
                                            score_name = getScoreNameFromRoundName(roundName)
                                        
                                        for performanceResultTable in data['performanceResultTables']:
                                            for performanceResultSet in performanceResultTable['resultSets']:
                                                if performanceResultSet['id'] == ruleResultSet['id']:
                                                    for ranking in performanceResultSet['primaryRanking']:

                                                        score_item = getScoreItemFromRanking(data, ranking, gymnasts, score_name, performanceResultTable['unitId'])
                                                        score_count += 1
                                                           
            print(f"{score_count} score items created and assigned to gymnasts")

            for gymnast in gymnasts:
                for performance in gymnast['performance_ids']:
                    if gymnast['discipline'] == 'WAG':

                        vt_scores = getAppScore(performance['scores'], 'vault')
                        ub_scores = getAppScore(performance['scores'], 'u-bars')
                        bb_scores = getAppScore(performance['scores'], 'beam')
                        fx_scores = getAppScore(performance['scores'], 'floor')
                        aa_scores = getAppScore(performance['scores'], 'all-around')
                        round_name = vt_scores["round_name"]

                        row = {
                            "gnz_id": gymnast['gnz_id'],
                            "gymnast_id": gymnast['participant_id'],
                            "name": gymnast['name'],
                            "discipline": gymnast['discipline'],
                            "level": gymnast['level'],
                            "division": gymnast['division'],
                            "club": gymnast['club'],
                            "competition": competition_name,
                            "round_name": round_name
                        }

                        row.update(vt_scores)
                        row.update(ub_scores)
                        row.update(bb_scores)
                        row.update(fx_scores)
                        if aa_scores is not None:
                            row.update(aa_scores)
                        else:
                            try:
                                dnf_aa_score = vt_scores["vault-score"] + ub_scores["u-bars-score"] + bb_scores["beam-score"] + fx_scores["floor-score"]
                            except TypeError:
                                dnf_aa_score = 0

                            dnf_result = {
                                "all-around-score": dnf_aa_score,
                                "all-around-rank": "DNF"
                            }
                            row.update(dnf_result)

                        wagResults.append(row)
                    elif gymnast['discipline'] == 'MAG':
                        fx_scores = getAppScore(performance['scores'], 'floor')
                        ph_scores = getAppScore(performance['scores'], 'pommel')
                        sr_scores = getAppScore(performance['scores'], 'rings')
                        vt_scores = getAppScore(performance['scores'], 'vault')
                        pb_scores = getAppScore(performance['scores'], 'p-bars')
                        hb_scores = getAppScore(performance['scores'], 'h-bar')
                        aa_scores = getAppScore(performance['scores'], 'all-around')
                        round_name = vt_scores["round_name"]

                        row = {
                            "gnz_id": gymnast['gnz_id'],
                            "gymnast_id": gymnast['participant_id'],
                            "name": gymnast['name'],
                            "discipline": gymnast['discipline'],
                            "level": gymnast['level'],
                            "division": gymnast['division'],
                            "club": gymnast['club'],
                            "competition": competition_name,
                            "round_name": round_name
                        }

                        row.update(fx_scores)
                        row.update(ph_scores)
                        row.update(sr_scores)
                        row.update(vt_scores)
                        row.update(pb_scores)
                        row.update(hb_scores)
                        
                        if aa_scores is not None:
                            row.update(aa_scores)
                        else:
                            dnf_aa_score = vt_scores["vault-score"] + fx_scores["floor-score"] + pb_scores["p-bars-score"] + sr_scores["rings-score"] + hb_scores["h-bar-score"] + ph_scores["pommel-score"]
                            dnf_result = {
                                "all-around-score": dnf_aa_score,
                                "all-around-rank": "DNF"
                            }
                            row.update(dnf_result)

                        magResults.append(row)

            
    wag_df = pd.DataFrame(wagResults)
    mag_df = pd.DataFrame(magResults)

    roundDataframes = {
        "WAG": wag_df,
        "MAG": mag_df
    }

    #output_name = competition_name.replace('|', '').replace('/', '') + '.xlsx'
    dataframes_to_xlsx(roundDataframes, "art-results.xlsx", OUTPUT_DIR)

    print("End")