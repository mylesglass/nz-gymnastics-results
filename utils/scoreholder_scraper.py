from ast import Name
import json
import re
import pandas as pd
import os

verbose = 1
source_dir = "json"
wag_header = ["gnz-id","name","club","step","division","competition","round-type", "day", "v-total","v-d","v-rank","ub-total","ub-d","ub-rank","bb-total","bb-d","bb-rank","fx-total","fx-d","fx-rank","aa-score","aa-rank","date-created"]
mag_header = ["gnz-id","name","club","step","division","competition","round-type","fx-total","fx-d","fx-e","ph-total","ph-d","ph-e","sr-total","sr-d","sr-e","vt-total","vt-d","vt-e","pb-total","pb-d","pb-e","hb-total","hb-d","hb-e","aa-score","aa-rank","date-created"]

def fixId(id):
    if id.startswith("GS"):
        return id[2:]
    elif id == "":
        return "000000"
    return id

def getClub(club_id):
    for club in clubs:
        if club_id == club['club_id']:
            return club['name']

    raise NameError("Couldn't find", club_id, "in club list.")

def getLevel(tags):
    
    for tag in tags:
        try:
            if 'international' in tag.lower() or 'open' in tag.lower() or 'u16' in tag.lower() or 'ji' in tag.lower() or 'si' in tag.lower():
                return tag
            if 'step' in tag.lower() or 'level' in tag.lower():
                return re.findall(r'\d+', tag)[0]
            # hack af
            #if tag == "1" or tag == "2" or tag == "3" or tag == "4" or tag == "5" or tag == "6" or tag == "7" or tag == "8" or tag == "9" or tag == "10":
            #    return re.findall(r'\d+', tag)[0]
            ##if "WAG" in tag or "MAG" in tag:
            ##    return re.findall(r'\d+', tag)[0]
        except:
            print(tag)
            raise NameError("Blaying Up", tags)

    raise NameError("No STEP / Level within these tags", tags)

def getDiscipline(tags):
    
    for tag in tags:
        if 'wag' in tag.lower() or 'step' in tag.lower():
            return 'WAG'
        elif 'mag' in tag.lower() or 'level' in tag.lower():
            return 'MAG'
    return 'None'

def getDivision(tags):
    for tag in tags:
        if 'under' in tag.lower() or tag == "U":
            return 'UNDER'
        elif 'over' in tag.lower() or tag == "O":
            return 'OVER'
    
    return "NONE"

# Start

for file in os.listdir(source_dir):
    if file.endswith('.json'):
        file_location = source_dir + "\\" + file

        json_file = open(file_location)

        data = json.load(json_file)

        # get some sweet meta
        competition = data['event']['name']
        competition_date = data['event']['startDate']
        print('Creating results tables for', competition, '...')

        clubs = []

        # get list of clubs
        for club in data['organizations']:
            org = {
                "club_id": club['_id'],
                "name": club['name']
            }
            clubs.append(org)

        gymnasts = []

        # get gymnasts
        for competitor in data['competitors']:

            try:
                gnz_id = fixId(competitor['number'])
            except KeyError:
                gnz_id = ""

            if len(competitor['tags']) is not 0:
                gymnast = {
                    "sh_id": competitor['_id'],
                    "gnzid": gnz_id,
                    "name": competitor['name'],
                    "club": getClub(competitor['organization']),
                    "level/step": getLevel(competitor['tags']),
                    "discipline": getDiscipline(competitor['tags']),
                    "division": getDivision(competitor['tags'])
                }
            else:
                gymnast = {
                    "sh_id": competitor['_id'],
                    "gnzid": gnz_id,
                    "name": competitor['name'],
                    "club": getClub(competitor['organization']),
                    "level/step": 'NONE',
                    "discipline": 'NONE',
                    "division": 'NONE'
                }

            gymnasts.append(gymnast)

        # create data structure for round
        for round in data['rounds']:
            rows = []

            round_name = round['name']
            discipline = round['discipline']

            print("Creating table for", discipline ,round_name, )

            for competitor in round['competitors']:
                current_gymnast = ''
                # get gymnast data
                for gymnast in gymnasts:
                    if gymnast['sh_id'] == competitor['id']:
                        current_gymnast = gymnast

                score_ids = competitor['results']['scores']            

                if discipline == 'WAG':

                    # create arrays to fill for each apparatus
                    # pattern: total - ex - d - p
                    vt_score = [0,0,0]
                    ub_score = [0,0,0]
                    bb_score = [0,0,0]
                    fx_score = [0,0,0]

                    twoVaults = False
                    vault_count = 0
                    if len(score_ids) == 5:
                        twoVaults = True

                    for score_id in score_ids:
                        for score in data['scores']:
                            if score_id == score['_id']:
                                # we're going to assume from a little bit of poking that scores attached to gymnast in round are the most recent revision
                                latest_score = score['history'][len(score['history']) -1]
                                if not latest_score['didNotStart']:
                                    match score['apparatus']:
                                        case 'VT':
                                            if twoVaults and vault_count == 1:
                                                avg_total = (vt_score[0] + latest_score['finalScore']) / 2
                                                avg_diff = (vt_score[1] + latest_score['difficultyScore']) / 2
                                                avg_e = (vt_score[2] + latest_score['executionScore']) / 2
                                                vt_score = [avg_total, avg_diff, 0]
                                                vault_count += 1

                                            elif twoVaults and vault_count == 0:
                                                vt_score = [latest_score['finalScore'],latest_score['difficultyScore'],0]
                                                vault_count += 1

                                            else:
                                                vt_score = [latest_score['finalScore'],latest_score['difficultyScore'], 0]
                                        case 'UB':
                                            ub_score = [latest_score['finalScore'],latest_score['difficultyScore'], 0]
                                        case 'BB':
                                            bb_score = [latest_score['finalScore'],latest_score['difficultyScore'], 0]
                                        case 'FX':
                                            fx_score = [latest_score['finalScore'],latest_score['difficultyScore'], 0]
                    
                    aa_score = format(vt_score[0] + ub_score[0] + bb_score[0] + fx_score[0], ".3f")

                    row = [current_gymnast['gnzid'], current_gymnast['name'], current_gymnast['club'], round['category'], current_gymnast['division'], competition, round_name, "", vt_score[0], vt_score[1], vt_score[2], ub_score[0], ub_score[1], ub_score[2], bb_score[0], bb_score[1], bb_score[2], fx_score[0], fx_score[1], fx_score[2], aa_score, "", competition_date]

                    rows.append(row)

                if discipline == 'MAG':
                    # create arrays to fill for each apparatus
                    # pattern: total - ex - d - p
                    fx_score = [0,0,0]
                    ph_score = [0,0,0]
                    sr_score = [0,0,0]
                    vt_score = [0,0,0]
                    pb_score = [0,0,0]
                    hb_score = [0,0,0]


                    twoVaults = False
                    vault_count = 0
                    if len(score_ids) == 7:
                        twoVaults = True

                    for score_id in score_ids:
                        for score in data['scores']:
                            if score_id == score['_id']:
                                # check for latest revision in score...
                                latest_score = score['history'][len(score['history']) -1]
                                if not latest_score['didNotStart']:
                                    match score['apparatus']:
                                        case 'FX':
                                            fx_score = [latest_score['finalScore'],latest_score['difficultyScore'],latest_score['executionScore']]
                                        case 'PH':
                                            ph_score = [latest_score['finalScore'],latest_score['difficultyScore'],latest_score['executionScore']]
                                        case 'SR':
                                            sr_score = [latest_score['finalScore'],latest_score['difficultyScore'],latest_score['executionScore']]
                                        case 'VT':
                                            if twoVaults and vault_count == 1:
                                                avg_total = (vt_score[0] + latest_score['finalScore']) / 2
                                                avg_diff = (vt_score[1] + latest_score['difficultyScore']) / 2
                                                avg_e = (vt_score[2] + latest_score['executionScore']) / 2
                                                vt_score = [avg_total, avg_diff, avg_e]
                                                vault_count += 1

                                            elif twoVaults and vault_count == 0:
                                                vt_score = [latest_score['finalScore'],latest_score['difficultyScore'],latest_score['executionScore']]
                                                vault_count += 1

                                            else:
                                                vt_score = [latest_score['finalScore'],latest_score['difficultyScore'],latest_score['executionScore']]
                                        case 'PB':
                                            pb_score = [latest_score['finalScore'],latest_score['difficultyScore'],latest_score['executionScore']]
                                        case 'HB':
                                            hb_score = [latest_score['finalScore'],latest_score['difficultyScore'],latest_score['executionScore']]
                    
                    aa_score = format(fx_score[0] + ph_score[0] + sr_score[0] + vt_score[0] + pb_score[0] + hb_score[0], ".3f")
                    row = [current_gymnast['gnzid'], current_gymnast['name'], current_gymnast['club'], round['category'], current_gymnast['division'], competition, round_name, fx_score[0], fx_score[1], fx_score[2], ph_score[0], ph_score[1], ph_score[2], sr_score[0], sr_score[1], sr_score[2], vt_score[0], vt_score[1], vt_score[2], pb_score[0], pb_score[1], pb_score[2], hb_score[0], hb_score[1], hb_score[2], aa_score, "", competition_date]

                    rows.append(row)

            df = pd.DataFrame(rows)
            if verbose: print(df)
            
            mypath = discipline
            if not os.path.isdir(mypath):
                os.makedirs(mypath)
            filename = discipline + "\\" + competition + " - " + discipline + " " + round['category'] + " " + round_name + ".csv"
            if discipline == "WAG":
                df.to_csv(filename, header=wag_header, index=False)
            if discipline == "MAG":
                df.to_csv(filename, header=mag_header)
            print(filename, "created.")
            print("------------------------------------------------------------------------------")