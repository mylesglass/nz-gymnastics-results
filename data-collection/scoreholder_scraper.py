from ast import Name
import json
import re
import pandas as pd
import os

verbose = 1
source_dir = "WAG 2023"
wag_header = ["gnz-id", "name", "club", "step", "division", "competition", "round-type", "day", "v-total", "v-d", "v-e", "v-n", "v-rank", "ub-total", "ub-d",
              "ub-e", "ub-n", "ub-rank", "bb-total", "bb-d", "bb-e", "bb-n", "bb-rank", "fx-total", "fx-d", "fx-e", "fx-n", "fx-rank", "aa-score", "aa-rank", "date-created"]
mag_header = ["gnz-id", "name", "club", "step", "division", "competition", "round-type", "fx-total", "fx-d", "fx-e", "fx-n", "fx-rank", "ph-total", "ph-d", "ph-e", "ph-n", "ph-rank", "sr-total", "sr-d",
              "sr-e", "sr-n", "sr-rank", "vt-total", "vt-d", "vt-e", "vt-n", "vt-rank", "pb-total", "pb-d", "pb-e", "pb-n", "pb-rank", "hb-total", "hb-d", "hb-e", "hb-n", "hb-rank", "aa-score", "aa-rank", "date-created"]


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


def getPlacing(app_results, code):
    for result in app_results:
        if result['code'] == code:
            # check if rank exists cause sometimes they don't *shrug*
            if len(result['ranks']) != 0:
                if result['ranks'][0] != {}:
                    return result['ranks'][0]['rank']
            else:
                return 0


def truncate(f, n):
    '''Truncates/pads a float f to n decimal places without rounding'''
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return '.'.join([i, (d+'0'*n)[:n]])


def formatScore(latest_score, placing):
    try:
        if latest_score.get('neutralDeductions') is not None:
            return [latest_score['finalScore'], latest_score['difficultyScore'], latest_score['executionScore'], latest_score['neutralDeductions'], placing]
        else:
            return [latest_score['finalScore'], latest_score['difficultyScore'], latest_score['executionScore'], 0, placing]
    except KeyError:
        print("KeyError in Formatting Score:", latest_score)
        return [0,0,0,0,0]

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

def notGFA(category):
    naughty_words = [
        'Bronze', 'Silver', 'Emerald', 'Gold', 'Grade', 'Iron', 'Ruby'
    ]


    for word in naughty_words:
        if word.lower() in category.lower():
            return False
        
    return True

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
            print(org['name'], "added to clubs list")
            clubs.append(org)

        gymnasts = []

        # get gymnasts
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

            if verbose:
                print(gymnast['name'], gymnast['level/step'],
                      gymnast['division'], "added to gymnast list")
            gymnasts.append(gymnast)

        # create data structure for round
        for round in data['rounds']:

            # check if GFA
            if notGFA(round['category']):

                rows = []

                round_name = round['name']
                discipline = round['discipline']

                print("Creating table for", discipline, round_name, )

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
                            print('KeyError getting AA Placing', competitor['results']['allAround']['ranks'])
                            aa_placing = 0
                        except IndexError:
                            print('IndexError getting AA Placing', competitor['results']['allAround']['ranks'])
                            aa_placing = 0

                    # Calculate All Around score and score row
                    if discipline == 'WAG':
                        aa_score = "{:.3f}".format(vt_score[0] + ub_score[0] + bb_score[0] + fx_score[0])
                        row = [current_gymnast['gnzid'], current_gymnast['name'], current_gymnast['club'], round['category'], current_gymnast['division'], competition, round_name, "", vt_score[0], vt_score[1], vt_score[2], vt_score[3], vt_score[4], ub_score[0], ub_score[1], ub_score[2], ub_score[3], ub_score[4], bb_score[0], bb_score[1], bb_score[2], bb_score[3], bb_score[4], fx_score[0], fx_score[1], fx_score[2], fx_score[3], fx_score[4], aa_score, aa_placing, timestamp]
                    if discipline == 'MAG':
                        aa_score = "{:.3f}".format(fx_score[0] + ph_score[0] + sr_score[0] + vt_score[0] + pb_score[0] + hb_score[0])
                        row = [current_gymnast['gnzid'], current_gymnast['name'], current_gymnast['club'], round['category'], current_gymnast['division'], competition, round_name, fx_score[0], fx_score[1], fx_score[2], fx_score[3], fx_score[4], ph_score[0], ph_score[1], ph_score[2], ph_score[3], ph_score[4], sr_score[0], sr_score[1], sr_score[2], sr_score[3], sr_score[4], vt_score[0], vt_score[1], vt_score[2], vt_score[3], vt_score[4], pb_score[0], pb_score[1], pb_score[2], pb_score[3], pb_score[4], hb_score[0], hb_score[1], hb_score[2], hb_score[3], hb_score[4], aa_score, aa_placing, timestamp]

                    rows.append(row)

                df = pd.DataFrame(rows)

                mypath = discipline
                if not os.path.isdir(mypath):
                    os.makedirs(mypath)
                filename = (discipline + "\\" + competition + " - " + discipline + \
                    " " + round['category'] + " " + round_name + ".csv").replace(':', '').replace('/', '+')
                try:
                    if discipline == "WAG":
                        df.to_csv(filename, header=wag_header, index=False)
                    if discipline == "MAG":
                        df.to_csv(filename, header=mag_header, index=False)
                    print(filename, "created.")
                except ValueError:
                    print("VALUE ERROR!!!!", filename, 'NOT SAVED TO CSV')
                print(
                    "------------------------------------------------------------------------------")
