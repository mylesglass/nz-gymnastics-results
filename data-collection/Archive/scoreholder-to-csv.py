from contextlib import nullcontext
from numpy import ubyte
import tabula
import pdfplumber
import pandas as pd
import re
import os
import time
from decimal import Decimal

start = time.time()
total_page_count = 0
total_file_count = 0
competition = ""
source_dir = "WAG 2023/2023 Central Champs"
page_count = 1
page_metas = []
wag_header = ["gnz-id","name","club","step","division","competition","round-type","day","v-total","v-d","v-rank","ub-total","ub-d","ub-rank","bb-total","bb-d","bb-rank","fx-total","fx-d","fx-rank","aa-score","aa-rank","date-created"]
mag_header = ["gnz-id","name","club","step","division","competition","round-type","day","fx-total","fx-d","fx-rank","ph-total","ph-d","ph-rank","sr-total","sr-d","sr-rank","vt-total","vt-d","vt-rank","pb-total","pb-d","pb-rank","hb-total","hb-d","hb-rank","aa-score","aa-rank","date-created"]
verbose = 1

def SkuxASCII():
    print("   _____ __________  ____  ________  ______  __    ____  __________     ____  ___    ____  _____ __________          ___")
    print("  / ___// ____/ __ \/ __ \/ ____/ / / / __ \/ /   / __ \/ ____/ __ \   / __ \/   |  / __ \/ ___// ____/ __ \   _   _<  /")
    print("  \__ \/ /   / / / / /_/ / __/ / /_/ / / / / /   / / / / __/ / /_/ /  / /_/ / /| | / /_/ /\__ \/ __/ / /_/ /  | | / / / ")
    print(" ___/ / /___/ /_/ / _, _/ /___/ __  / /_/ / /___/ /_/ / /___/ _, _/  / ____/ ___ |/ _, _/___/ / /___/ _, _/   | |/ / /  ")
    print("/____/\____/\____/_/ |_/_____/_/ /_/\____/_____/_____/_____/_/ |_|  /_/   /_/  |_/_/ |_|/____/_____/_/ |_|    |___/_/   ")
                                                                                                                        
def GetPageRoundType(page):
    div_type = ""
    div_type_bbox = (401, 40, 820, 50)
    for char in page.crop(div_type_bbox, relative=False).chars:
        div_type = div_type + char.get('text', 'X')
    return div_type

def GetPageType(page):
    page_type = ""
    page_type_bbox = (0, 28, 400, 50)
    for char in page.crop(page_type_bbox, relative=False).chars:
        page_type = page_type + char.get('text', 'X')
    return page_type

def GetRoundType(page_type):
    app_variations = ["Apparatus","apparatus"]
    aa_variations = ["all around", "allaround", "all round"]
    team_variations = ["Team","team"]

    for variation in app_variations:
        if variation in page_type:
            return "APP"
    for variation in aa_variations:
        if variation in page_type.lower():
            return "AA"
    for variation in team_variations:
        if variation in page_type:
            return "TEAM"

def GetCompName(page):
    comp_name = ""
    comp_name_bbox = (516, 28, 820, 36)
    for char in page.crop(comp_name_bbox, relative=False).chars:
        if char.get('text', 'X') == "\\" or char.get('text', 'X') == "/":
            comp_name = comp_name + "-"
        else:
            comp_name = comp_name + char.get('text', 'X')

    return comp_name

def GetDiscipline(pageround_type):
    if "WAG" in pageround_type:
        return "WAG"
    elif "MAG" in pageround_type:
        return "MAG"

def GetLevel(pageround_type):
    int_variations = ["junior international", "senior international", "ji", "si", "jnr int", "snr int", "senior"]
    for variation in int_variations:
        if variation in pageround_type.lower():
            return variation

    return re.findall(r'\d+', pageround_type)[0]

def GetDivision(pageround_type):
    over_variations = ["OVER","over","Over"]
    under_variations = ["UNDER", "Under", "under", "Double Under", "double under", "Double under"]
    
    for variation in over_variations:
        if variation in pageround_type:
            return "OVER"

    for variation in under_variations:
        if variation in pageround_type:
            return "UNDER"
    
    return "NONE"

def GetMultiPage(number, type):
    if number != 1:
        previous_page = GetPage(number - 1)
        if previous_page.pageround_type == type:
            return True
    else:
        return 0

def GetCreated(page):
    created = ""
    created_bbox = (0, 570, 500, 595)
    for char in page.crop(created_bbox, relative=False).chars:
        created = created + char.get('text', 'X')
    return created[32:]

def GetDay(pageround_type, page_number):
    for meta in page_metas:
        #dont think this works yet bro
        if meta.pageround_type == pageround_type and meta.round_type == "AA" and meta.page_number != page_number:
            return 2
        else:
            return 1

def IsAppFinal(pageround_type):
    aa_vars =["all around", "aa"]

    for str in aa_vars:
        if str in pageround_type.lower():
            return False
    
    return True

def GetApparatus(discpline, pageround, pagetype):
    vault_strings = ["vault","vt"]
    floor_strings = ["floor", "fx", "floor exercise"]
    beam_strings = ["beam", "balance beam", "bb"]
    pommel_strings = ["pommel", "ph", "horse"] # 'ph' might cause errors
    rings_strings = ["rings","sr","still rings"]

    if IsApp(vault_strings, pageround, pagetype):
        return "VT"

    if IsApp(floor_strings, pageround, pagetype):
        return "FX"

    if IsApp(beam_strings, pageround, pagetype):
        return "BB"

    if IsApp(pommel_strings, pageround, pagetype):
        return "PH"

    if IsApp(rings_strings, pageround, pagetype):
        return "SR"

    if discpline == "WAG":
        bars_strings = ["bars", "ub", "u-bars", "uneven bars"]
        if IsApp(bars_strings, pageround, pagetype):
            return "UB"

    if discpline == "MAG":
        pbar_strings = ["p-bar", "pb", "parallel"]
        hbar_strings = ["h-bar", "hb", "horizontal", "high"]

        if IsApp(pbar_strings, pageround, pagetype):
            return "PB"

        if IsApp(hbar_strings, pageround, pagetype):
            return "HB"
    else:
        return None

def IsApp(strings, pageround, pagetype):
    for str in strings:
        if str in pageround.lower() or str in pagetype.lower():
            return True
    return False
    
class PageMeta:
    def __init__(self, page, page_number):
        self.comp_name = GetCompName(page)
        self.page_type = GetPageType(page)
        self.pageround_type = GetPageRoundType(page)
        self.round_type = GetRoundType(self.page_type)
        self.discipline = GetDiscipline(self.pageround_type)
        self.level = GetLevel(self.pageround_type)
        self.division = GetDivision(self.pageround_type)
        self.page_number = page_number
        self.multipage = GetMultiPage(self.page_number, self.pageround_type)
        self.created = GetCreated(page)
        self.day = GetDay(self.pageround_type, page_number)
        self.apparatus_final = IsAppFinal(self.pageround_type)
        self.apparatus = GetApparatus(self.discipline, self.pageround_type, self.page_type)

def printMeta(metaObj):
    print("---------------------")
    print("Metadata for page number ", metaObj.page_number)
    print("Competition: ", metaObj.comp_name)
    print("Page Type: ", metaObj.page_type)
    print("Page Round Type: ", metaObj.pageround_type)
    print("Round Type: ", metaObj.round_type)
    print("Discipline: ", metaObj.discipline)
    print("Level/STEP: ", metaObj.level)
    print("Division: ", metaObj.division)
    print("Is Multi Page?", metaObj.multipage)
    print("Day", metaObj.day)
    print("App Final?", metaObj.apparatus_final)
    print("Apparatus:", metaObj.apparatus)
    print("---------------------")

def GetPage(page_number):
    return page_metas[page_number - 1]

def FixAppScore(raw_score):
    print(raw_score)
    if raw_score != "DNS" and raw_score != "" and raw_score != " ":
        split = raw_score.split()
        split[1] = split[1].replace("(","").replace(")","")
        return split
    else:
        return ["DNS","DNS","DNS"] # hacky, do not change

def GetAppFinalScore(row):
    if row != None:
        if row[0] == "-":
            return ["DNS","DNS","DNS"]
        else:
            return [row[7], row[4], row[0]]
    return ["DNS","DNS","DNS"]

def FixID(id):
    if id.startswith("GS"):
        return id[2:]
    elif id == "":
        return "000000"
    return id

def AddRows(table, meta):

    list = []

    # set iterator to start after headers of table
    i = 2

    while i < len(table):
        row = table[i]
        print(row)
        nameclub = row[2].splitlines()
        # remove placing from score
        if meta.discipline == "WAG":
            vt = FixAppScore(row[3])
            ub = FixAppScore(row[6])
            bb = FixAppScore(row[9])
            fx = FixAppScore(row[12])
            data = [FixID(row[1]),nameclub[0],nameclub[1],meta.level,meta.division,meta.comp_name,meta.round_type,meta.day,vt[0],vt[2],vt[1],ub[0],ub[2],ub[1],bb[0],bb[2],bb[1],fx[0],fx[2],fx[1],row[15],row[0],meta.created]
            list.append(data)
            i += 1
        
        if meta.discipline == "MAG":
            data = []

            if meta.level != '1':
                fx = FixAppScore(row[3])
                ph = FixAppScore(row[6])
                sr = FixAppScore(row[9])
                vt = FixAppScore(row[12])
                pb = FixAppScore(row[15])
                hb = FixAppScore(row[18])
                data = [FixID(row[1]),nameclub[0],nameclub[1],meta.level,meta.division,meta.comp_name,meta.round_type,meta.day,fx[0],fx[2],fx[1],ph[0],ph[2],ph[1],sr[0],sr[2],sr[1],vt[0],vt[2],vt[1],pb[0],pb[2],pb[1],fx[0],fx[2],fx[1],row[21],row[0],meta.created]

            else:
                fx = FixAppScore(row[3])
                ph = ["DNS","DNS","DNS"]
                sr = FixAppScore(row[6])
                vt = FixAppScore(row[9])
                pb = FixAppScore(row[12])
                hb = FixAppScore(row[15])
                data = [FixID(row[1]),nameclub[0],nameclub[1],meta.level,meta.division,meta.comp_name,meta.round_type,meta.day,fx[0],fx[2],fx[1],ph[0],ph[2],ph[1],sr[0],sr[2],sr[1],vt[0],vt[2],vt[1],pb[0],pb[2],pb[1],fx[0],fx[2],fx[1],row[18],row[0],meta.created]

            
            list.append(data)
            i += 1
    return list

def CalcWAGAA(vt, ub, bb, fx):
    score = 0

    if vt == "DNS":
        score += 0
    else: 
        score += Decimal(vt)

    if ub == "DNS":
        score += 0
    else: 
        score += Decimal(ub)

    if bb == "DNS":
        score += 0
    else: 
        score += Decimal(bb)

    if fx == "DNS":
        score += 0
    else: 
        score += Decimal(fx)

    return score

def CalcMAGAA(fx, ph, sr, vt, pb, hb):
    score = 0    

    if fx == "DNS":
        score += 0
    else: 
        score += Decimal(fx)

    if ph == "DNS":
        score += 0
    else: 
        score += Decimal(ph)

    if sr == "DNS":
        score += 0
    else: 
        score += Decimal(sr)

    if vt == "DNS":
        score += 0
    else: 
        score += Decimal(vt)

    if pb == "DNS":
        score += 0
    else: 
        score += Decimal(pb)

    if hb == "DNS":
        score += 0
    else: 
        score += Decimal(hb)

    return score

def GetGymnastRowFromTable(page, gymnast):
    table = page.extract_table()

    i = 1

    while i < len(table):
        row = table[i]
        if gymnast[0] == row[1]:
            return row
        i += 1

    return ['-', gymnast[0], gymnast[1], gymnast[2], 'DNS', 'DNS', '', 'DNS']
    print("you def shouldn't see this yo")

def GetTwoVaultScore(row):
    if row != None:
        if row[0] == "-":
            return ["DNS","DNS","DNS"]
        else:
            return [row[9], 0, row[0]]
    return ["DNS","DNS","DNS"]

def IsTwoVaults(row):
    if len(row) == 8:
        return False
    elif len(row) > 8:
        return True
    else:
        print("dogg i dont even know")

# run program etc
SkuxASCII()
print("Finding files in", source_dir)

# detect pdfs in directory
pdf_files = os.listdir(source_dir)

# for each pdf file
for file in pdf_files:
    if file.endswith(".pdf"):
        total_file_count += 1
        page_count = 1
        page_metas = []

        file_location = source_dir + "\\" + file

        # open pdfs with pdfplumber
        with pdfplumber.open(file_location) as pdf:
            print("Opening", file_location)
            
            print("Processing metadata of document...")
            for page in pdf.pages:
                if page.width < 600:
                    print("Incorrect Dimensions for Parsing!")
                else:
                    page_metas.append(PageMeta(page, page_count))
                    page_count = page_count + 1
                    total_page_count += 1

            if verbose:
                for i in range(1, page_count):
                    printMeta(GetPage(i))

            print("Pulled metadata from", page_count - 1, "pages in document", file_location)

            app_finals = []
            
            for meta in page_metas:
                # All Around Results
                
                if meta.round_type == "AA" and meta.multipage != True:

                    if verbose:
                        printMeta(meta)
                    page = pdf.pages[meta.page_number - 1] # account for index from 0
                    table = page.extract_table()

                    # empty list to fill with data
                    rows = []
                    
                    # check how many pages of results there are for this AA comp
                    aa_pages_count = 1
                    i = 1
                    total_pages_in_pdf = len(page_metas)

                    # add rows from table (excluding headers)
                    rows.extend(AddRows(table, meta))

                    # if this page is less than the total number of pages in the document.. (otherwise it must be last page)
                    if total_pages_in_pdf > meta.page_number:

                        next_meta = page_metas[meta.page_number]

                        # if the PAGE 2 is flagged as multipage AND AA
                        if next_meta.multipage and next_meta.round_type == "AA" and meta.pageround_type == next_meta.pageround_type:
                            next_table = pdf.pages[meta.page_number].extract_table()
                            rows.extend(AddRows(next_table, next_meta))

                            # is it possible for there to be a next page?
                            next_page_number = meta.page_number + 1
                            try:
                                next_meta = page_metas[next_page_number]
                                if total_pages_in_pdf > next_page_number:

                                    # if the PAGE 3 is flagged as multipage AND AA
                                    if next_meta.multipage and next_meta.round_type == "AA" and meta.pageround_type == next_meta.pageround_type:
                                        next_table = pdf.pages[next_page_number].extract_table()
                                        rows.extend(AddRows(next_table, next_meta))
                            except IndexError:
                                print("err... carry on?")

                    # create the dataframe thang
                    df = pd.DataFrame(rows)
                    print(df)

                    # output
                    mypath = meta.discipline
                    if not os.path.isdir(mypath):
                        os.makedirs(mypath)
                    filename = meta.discipline + "\\" + meta.comp_name + " - " + meta.pageround_type + ".csv"
                    if meta.discipline == "WAG":
                        df.to_csv(filename, header=wag_header, index=False)
                    if meta.discipline == "MAG":
                        df.to_csv(filename, header=mag_header)
                    print(filename, "created.")
                    print("------------------------------------------------------------------------------")
                
                # Get Apparatus Finals
                
                if meta.apparatus_final:
                    app_finals.append(meta)

            for app_final in app_finals:

                # BUG: if there's not an vault sheet (i.e. no one competes vault in app final and it isn't created) we never get through this gate
                if "Vault" in app_final.page_type or "Vault" in app_final.pageround_type:

                    if verbose:
                        print("Creating table for:")
                        printMeta(app_final)
                    page = pdf.pages[app_final.page_number - 1] # account for index from 0
                    table = page.extract_table()

                    gymnasts = []
                    i = 1
                    while i < len(table):
                        row = table[i]
                        gymnast_obj = [row[1], row[2], row[3], app_final.comp_name, app_final.round_type]
                        gymnasts.append(gymnast_obj)
                        i += 1

                    # empty list to fill with data
                    rows = []

                    # build a row for each gymnast & add to stack
                    for gymnast in gymnasts:

                        if app_final.discipline == "WAG":
                            i = 1
                            vt = ["DNS","DNS","DNS"]
                            ub = ["DNS","DNS","DNS"]
                            bb = ["DNS","DNS","DNS"]
                            fx = ["DNS","DNS","DNS"]
                            
                            while i < len(table):
                                row = table[i]
                                if gymnast[0] == row[1]:
                                    # identify if vault final competed 2 vaults (STEP 10, Int etc)
                                    if IsTwoVaults(row):
                                        vt = GetTwoVaultScore(row)
                                    else:
                                        vt = GetAppFinalScore(row)
                                i += 1

                            for other_app_final in app_finals: # search other app finals
                                if app_final.level == other_app_final.level and other_app_final.division == app_final.division: # filter for same level & division
                                    if other_app_final.apparatus == "UB":
                                        #get row with gymnast id
                                        row = GetGymnastRowFromTable(pdf.pages[other_app_final.page_number - 1], gymnast)
                                        if verbose: print("ub app score for", gymnast[2], row)
                                        ub = GetAppFinalScore(row)

                                    if other_app_final.apparatus == "BB":
                                        #get row with gymnast id
                                        row = GetGymnastRowFromTable(pdf.pages[other_app_final.page_number - 1], gymnast)
                                        if verbose: print("bb app score for", gymnast[2], row)
                                        bb = GetAppFinalScore(row)

                                    if other_app_final.apparatus == "FX":
                                        #get row with gymnast id
                                        row = GetGymnastRowFromTable(pdf.pages[other_app_final.page_number - 1], gymnast)
                                        if verbose: print("fx app score for", gymnast[2], row)
                                        fx = GetAppFinalScore(row)
                            
                            aa = CalcWAGAA(vt[0], ub[0], bb[0], fx[0])
                            app_final_row = [FixID(row[1]), row[3], row[2], app_final.level, app_final.division, app_final.comp_name, "APP", app_final.day, vt[0], vt[1], vt[2], ub[0], ub[1], ub[2], bb[0], bb[1], bb[2], fx[0], fx[1], fx[2], aa, "", app_final.created]
                            rows.append(app_final_row)

                        if app_final.discipline == "MAG":
                            i = 1
                            fx = None
                            ph = None
                            sr = None
                            vt = None
                            pb = None
                            hb = None

                            while i < len(table):
                                row = table[i]

                                if gymnast[0] == row[1]:
                                    # identify if vault final competed 2 vaults (STEP 10, Int etc)
                                    if IsTwoVaults(row):
                                        vt = GetTwoVaultScore(row)
                                    else:
                                        vt = GetAppFinalScore(row)
                                i += 1

                            for other_app_final in app_finals: # search other app finals
                                if app_final.level == other_app_final.level: # filter for same level
                                    if other_app_final.apparatus == "FX":
                                        #get row with gymnast id
                                        row = GetGymnastRowFromTable(pdf.pages[other_app_final.page_number - 1], gymnast)
                                        if verbose: print("fx", row)
                                        fx = GetAppFinalScore(row)

                                    if other_app_final.apparatus == "PH":
                                        #get row with gymnast id
                                        row = GetGymnastRowFromTable(pdf.pages[other_app_final.page_number - 1], gymnast)
                                        if verbose: print("ph", row)
                                        ph = GetAppFinalScore(row)

                                    if other_app_final.apparatus == "SR":
                                        #get row with gymnast id
                                        row = GetGymnastRowFromTable(pdf.pages[other_app_final.page_number - 1], gymnast)
                                        if verbose: print("sr", row)
                                        sr = GetAppFinalScore(row)
                                    
                                    if other_app_final.apparatus == "PB":
                                        #get row with gymnast id
                                        row = GetGymnastRowFromTable(pdf.pages[other_app_final.page_number - 1], gymnast)
                                        if verbose: print("pb", row)
                                        pb = GetAppFinalScore(row)

                                    if other_app_final.apparatus == "HB":
                                        #get row with gymnast id
                                        row = GetGymnastRowFromTable(pdf.pages[other_app_final.page_number - 1], gymnast)
                                        if verbose: print("hb", row)
                                        hb = GetAppFinalScore(row)
                                    
                            aa = CalcMAGAA(fx[0], ph[0], sr[0], vt[0], pb[0], hb[0])
                            app_final_row = [FixID(row[1]), row[3], row[2], app_final.level, app_final.division, app_final.comp_name, "APP", app_final.day, fx[0], fx[1], fx[2], ph[0], ph[1], ph[2], sr[0], sr[1], sr[2], vt[0], vt[1], vt[2], pb[0], pb[1], pb[2], hb[0], hb[1], hb[2], aa, "", app_final.created]
                            rows.append(app_final_row)
                            
                    # create the dataframe thang
                    df = pd.DataFrame(rows)
                    print(df)

                    # output
                    mypath = app_final.discipline
                    if not os.path.isdir(mypath):
                        os.makedirs(mypath)
                    filename = app_final.discipline + "\\" + app_final.comp_name + " - " + app_final.pageround_type + "APP-FINAL.csv"
                    if app_final.discipline == "WAG":
                        df.to_csv(filename, header=wag_header, index=False)
                    if app_final.discipline == "MAG":
                        df.to_csv(filename, header=mag_header)
                    print(filename, "created.")
                    print("------------------------------------------------------------------------------")

print('Finished. It took {0:0.1f} seconds'.format(time.time() - start), 'to process', total_page_count, 'pages from', total_file_count, 'files')
