import requests
from bs4 import BeautifulSoup
import re
import csv
from collections import defaultdict
import pandas as pd
import os
import argparse
import numpy as np
from datetime import datetime
from datetime import date
import logging

def get_leg(year):
    leg_session = requests.get(f'https://legislature.idaho.gov/sessioninfo/{year}/legislation/')

    soup = BeautifulSoup(leg_session.content, "html.parser")

    # Return all <a> tags with this href, i.e. find all links to legislation on the page; should give complete legislation list for the session
    if int(year) > 2008:
        text = soup.find_all("a", href = re.compile(fr"/sessioninfo/{year}/legislation/[H|S]"))
    else:
        text = soup.find(id="hcode-tab-style2legislation-by-number")
        text = text.find_all("a", href = re.compile(fr"/sessioninfo/{year}/legislation/[H|S]"))

    leg_list = []

    # Create dictionary (allows for removal of most duplicates) and then create list
    leg_dict = defaultdict(int)
    for i in text:
        leg_dict[i] += 1
    for key in leg_dict:
        leg_num = str(key).strip('</a>')
        leg_num = leg_num.split('>', 1)[-1]
        if len(str(leg_num)) < 7:
            leg_list.append(leg_num)
    # Remove remaining duplicates
    leg_list = list(dict.fromkeys(leg_list))

    return leg_list

def create_df(leg_list, year):
    # Create dataframes from all_members excel and bill info csv
    member_df = pd.read_excel('all_members.xlsx', sheet_name = f'{year}')
    bill_df = pd.read_csv(f'coding_votes/coding_{year}_votes.csv', index_col = 'bill_num')

    # Create dataframe that will hold vote count
    vote_df = member_df.copy()
    for i in vote_df.index:
        vote_df.loc[i, 'LastName'] = vote_df.loc[i, 'Name'].split()[-1]
        if vote_df.loc[i, 'Positions'] == "Speaker of the House":
            vote_df.loc[i, 'LastName'] = "Speaker"

    vote_df.replace({np.NaN: None}, inplace=True)

    # Create dict of duplicate last names and districts
    # Necessary because district number sometimes omitted
    dup_names = vote_df[['LastName', 'District', 'Chamber', 'PartialSession']]
    dup_names = dup_names.fillna({"PartialSession":""})

    h_dup_names = dup_names[dup_names.Chamber == "House"]
    h_dup_names = h_dup_names[['LastName', 'District', 'PartialSession']]
    h_dup_names = h_dup_names[h_dup_names.duplicated(subset='LastName', keep=False)]
    h_dup_names.drop_duplicates(keep='last', inplace=True)
    h_dup_names = h_dup_names[h_dup_names.groupby('LastName').LastName.transform(len) > 1]
    h_dup_names.sort_values(by=['LastName'], inplace=True, ignore_index=True)

    s_dup_names = dup_names[dup_names.Chamber == "Senate"]
    s_dup_names = s_dup_names[['LastName', 'District', 'PartialSession']]
    s_dup_names = s_dup_names[s_dup_names.duplicated(subset='LastName', keep=False)]
    s_dup_names.drop_duplicates(keep='last', inplace=True)
    s_dup_names = s_dup_names[s_dup_names.groupby('LastName').LastName.transform(len) > 1]
    s_dup_names.sort_values(by=['LastName'], inplace=True, ignore_index=True)

    # Get votes
    for leg in leg_list:
        # Get webpage text
        vote_page = requests.get(f'https://legislature.idaho.gov/sessioninfo/{year}/legislation/{str(leg)}/')
        if vote_page.status_code != 404:
            soup = BeautifulSoup(vote_page.content, "html.parser")
            if int(year) < 2009:
                bill_page_text = str((soup.find_all("pre"))[0])
            else:
                bill_page_text = soup.find_all("tr")
                bill_page_text = list(map(lambda x: x.text, bill_page_text))
                bill_page_text = str(" ".join(bill_page_text))
                bill_page_text = bill_page_text.replace("\xa0", " ")

            # Get votes only if a vote happened
            house_vote_dict = {}
            senate_vote_dict = {}

            if "voice vote" in bill_page_text.lower() or "ayes" in bill_page_text.lower():
                # Get vote dates from bill_df
                # For some reason, 2010 and 2011 are reading in with different date formats
                try:
                    if year != '2010' and year != '2011':
                        house_vote_date = datetime.strptime(str(bill_df.loc[leg, 'house_vote_date']), "%Y-%m-%d").date()
                        house_vote_date2 = house_vote_date.strftime('%m/%d')
                    else:
                        house_vote_date = datetime.strptime(str(bill_df.loc[leg, 'house_vote_date']), "%d/%m/%Y").date()
                        house_vote_date2 = house_vote_date.strftime('%m/%d')
                except:
                    house_vote_date = None
                try:
                    if year != '2010' and year != '2011':
                        senate_vote_date = datetime.strptime(str(bill_df.loc[leg, 'senate_vote_date']), "%Y-%m-%d").date()
                        senate_vote_date2 = senate_vote_date.strftime('%m/%d')
                    else:
                        senate_vote_date = datetime.strptime(str(bill_df.loc[leg, 'senate_vote_date']), "%d/%m/%Y").date()
                        senate_vote_date2 = senate_vote_date.strftime('%m/%d')
                except:
                    senate_vote_date = None


                # Create dict of house votes
                # Manually skip S1280 from 1999--house votes cut off in middle
                if house_vote_date != None and (year != '1999' or leg != 'S1280'):
                    house_text = bill_page_text.split(house_vote_date2)[1:]
                    house_text = " ".join(house_text)
                    vote_type = (re.findall('(ayes|voice vote)', house_text.lower()))[0]

                    if vote_type == 'voice vote' or (vote_type == 'ayes' and "Abs/Excd" in house_text and ("R" in leg or "P" in leg or "M" in leg)):
                        #vote_df.loc[vote_df.Chamber=="House", leg] = "Voice Vote - Passed"
                        house_only = vote_df[vote_df.Chamber == 'House']
                        for i in house_only.index:
                            house_vote_dict[f'{house_only.loc[i, "LastName"]}'] = "Voice Vote - Passed"
                        district = None
                    else:
                        aye_index = house_text.find("AYES")
                        nay_index = house_text.find("NAY")
                        absent_index = house_text.find("Absent")
                        excused_index = house_text.find("Excused from voting")
                        floor_sponsor_index = house_text.find("Floor ")
                        if floor_sponsor_index == -1 or floor_sponsor_index > absent_index + 300:
                            floor_sponsor_index = house_text.find("Title ")
                        aye_list = (house_text[aye_index:nay_index]).replace("AYES", "", 1).strip().strip('–').strip('--').strip().split(' ')
                        aye_list = list(map(lambda x: x.strip(',').strip().strip(","), aye_list))
                        nay_list = (house_text[nay_index:absent_index]).replace("NAYS", "", 1).strip().strip('–').strip('--').strip().split(' ')
                        nay_list = list(map(lambda x: x.strip(',').strip().strip(","), nay_list))
                        if excused_index != -1:
                            absent_list = (house_text[absent_index:excused_index]).replace("Absent and excused", "", 1).replace('Absent', "", 1).strip().strip('–').strip('--').strip().split(' ')
                            absent_list = list(map(lambda x: x.strip(',').strip().strip(","), absent_list))
                            excused_list = (house_text[excused_index:floor_sponsor_index]).replace("Excused from voting", '', 1).strip().strip('–').strip('--').strip().split(' ')
                            excused_list = list(map(lambda x: x.strip(',').strip().strip(","), excused_list))
                        else:
                            absent_list = (house_text[absent_index:floor_sponsor_index]).replace("Absent and excused", "", 1).replace('Absent', "", 1).strip().strip('–').strip('--').strip().split(' ')
                            absent_list = list(map(lambda x: x.strip(',').strip().strip(","), absent_list))
                            excused_list = []
                        aye_list = [x for x in aye_list if x != "None" and x != ""]
                        nay_list = [x for x in nay_list if x != "None" and x != ""]
                        absent_list = [x for x in absent_list if x != "None" and x != ""]
                        excused_list = [x for x in excused_list if x !='None' and x != '']


                        # If both votes are on the same day, check the number of names to make sure house is house and sen is sen
                        # Use 55 as threshold
                        while len(aye_list) + len(nay_list) + len(absent_list) + len(excused_list) < 55:
                            house_text = house_text[floor_sponsor_index+5:]
                            aye_index = house_text.find("AYES")
                            nay_index = house_text.find("NAY")
                            absent_index = house_text.find("Absent")
                            excused_index = house_text.find("Excused from voting")
                            floor_sponsor_index = house_text.find("Floor ")
                            if floor_sponsor_index == -1 or floor_sponsor_index > absent_index + 300:
                                floor_sponsor_index = house_text.find("Title ")
                            aye_list = (house_text[aye_index:nay_index]).replace("AYES", "", 1).strip().strip('–').strip('--').strip().split(' ')
                            aye_list = list(map(lambda x: x.strip(',').strip().strip(","), aye_list))
                            nay_list = (house_text[nay_index:absent_index]).replace("NAYS", "", 1).strip().strip('–').strip('--').strip().split(' ')
                            nay_list = list(map(lambda x: x.strip(',').strip().strip(","), nay_list))
                            if excused_index != -1:
                                absent_list = (house_text[absent_index:excused_index]).replace("Absent and excused", "", 1).replace('Absent', "", 1).strip().strip('–').strip('--').strip().split(' ')
                                absent_list = list(map(lambda x: x.strip(',').strip().strip(","), absent_list))
                                excused_list = (house_text[excused_index:floor_sponsor_index]).replace("Excused from voting", "", 1).strip().strip('–').strip('--').strip().split(' ')
                                excused_list = list(map(lambda x: x.strip(',').strip().strip(","), excused_list))
                            else:
                                absent_list = (house_text[absent_index:floor_sponsor_index]).replace("Absent and excused", '', 1).replace('Absent', "", 1).strip().strip('–').strip('--').strip().split(' ')
                                absent_list = list(map(lambda x: x.strip(',').strip().strip(","), absent_list))
                                excused_list = []
                            aye_list=  [x for x in aye_list if x != "None" and x != ""]
                            nay_list = [x for x in nay_list if x != "None" and x != ""]
                            absent_list = [x for x in absent_list if x != "None" and x != ""]
                            excused_list = [x for x in excused_list if x !='None' and x != '']

                        for name in aye_list:
                            house_vote_dict[name] = "Aye"
                        for name in nay_list:
                            house_vote_dict[name] = "Nay"
                        for name in absent_list:
                            house_vote_dict[name] = "Absent"
                        for name in excused_list:
                            house_vote_dict[name] = "Excused from voting"

                        commas = []
                        for key in house_vote_dict.keys():
                            if "," in key:
                                commas.append(key)

                        for comma in commas:
                            pt1 = comma.split(",")[0]
                            pt2 = comma.split(",")[1]
                            house_vote_dict[pt1] = house_vote_dict[comma]
                            house_vote_dict[pt2] = house_vote_dict.pop(comma)


                    #2003
                    new_key = None
                    if "Nacarrato" in list(house_vote_dict.keys()):
                        house_vote_dict['Naccarato'] = house_vote_dict.pop('Nacarrato')
                    else:
                        for key in house_vote_dict:
                            if "Nacarrato" in key:
                                old_key = key
                                new_key = key.replace("Nacarrato", "Naccarato")
                        if new_key !=None:
                            house_vote_dict[new_key] = house_vote_dict.pop(old_key)

                    # Add votes to vote_df
                    for each_name in house_vote_dict:
                        name = each_name

                        if "Voice Vote - Passed" not in house_vote_dict.values():
                            # Split by parenthesis to create list of names to avoid partial string matching (e.g. Field in Fields)
                            name = name.split("(")
                            name = list(map(lambda x: x.strip("() ,"), name))
                            name = [x for x in name if x != ""]

                            district = None
                            if any(item in h_dup_names['LastName'].tolist() for item in name):
                                try:
                                    for d in name:
                                        if ")" in d:
                                            d = d.split(')')[0]
                                        if all(map(str.isdigit, d)):
                                            district = d
                                    district = int(district)
                                except:
                                    for item in name:
                                        if item in h_dup_names['LastName'].tolist():
                                            final_name = item

                                    dup_name_only = h_dup_names[h_dup_names.LastName == final_name]

                                    if len(dup_name_only['District'].unique())==1:
                                        district = dup_name_only['District'].unique()[0]

                                    else:
                                        dist_nums = h_dup_names[h_dup_names.LastName == final_name]
                                        dist_nums = dist_nums['District'].tolist()
                                        all_names = list(house_vote_dict.keys())
                                        all_names = [x for x in all_names if final_name in x]
                                        all_names = [x for x in all_names if any(map(str.isdigit, x))]
                                        all_names = list(map(lambda x: ''.join(re.findall('\d+', x)), all_names))
                                        all_names = list(map(lambda x: int(x), all_names))
                                        missing_dist = [x for x in dist_nums if x not in all_names]

                                        # If none of the duplicate last names are temp legislators
                                        if (all('Acting Senator' not in x for x in dup_name_only['PartialSession'].tolist()) and all("Acting Representative" not in x for x in dup_name_only['PartialSession'].tolist()) and all('Temporary Absence' not in x for x in dup_name_only['PartialSession'].tolist())) or len(missing_dist)==1:
                                            district = missing_dist[0]

                                        # If some of the duplicate last names are temp legislators
                                        elif (any('Acting Senator' in x for x in dup_name_only['PartialSession'].tolist()) or any("Acting Representative" in x for x in dup_name_only['PartialSession'].tolist()) or any('Temporary Absence' in x for x in dup_name_only['PartialSession'].tolist())) and len(missing_dist) > 1:
                                            all_names2 = list(house_vote_dict.keys())
                                            all_names2 = [x for x in all_names2 if final_name in x]
                                            all_names2 = [x for x in all_names2 if not any(map(str.isdigit, x))]
                                            if "(" in each_name:
                                                try:
                                                    all_names2.remove(final_name)
                                                    for name1 in all_names2:
                                                        ind_name = name1.split("(")
                                                        ind_name = list(map(lambda x: x.strip("() ,"), name))
                                                        ind_name = [x for x in name if x != ""]
                                                        # (Note: length of ind_name should never exceed 2)
                                                        dist_nums1 = dup_names[dup_names.Chamber == 'House']
                                                        dist_nums1 = dist_nums1[dist_nums1.LastName == ind_name[0]]
                                                        dist_nums1 = dist_nums1['District'].tolist()
                                                        dist_nums2 = dup_names[dup_names.Chamber == 'House']
                                                        dist_nums2 = dist_nums2[dist_nums2.LastName == ind_name[1]]
                                                        dist_nums2 = dist_nums2['District'].tolist()

                                                        match = [x for x in dist_nums1 if x in dist_nums2]

                                                        district = match[0]
                                                except:
                                                    logging.info(f'ERROR: Unable to detect correct district for {each_name}.')

                                            else:
                                                remove_temps = h_dup_names[h_dup_names.LastName == final_name]
                                                remove_temps = remove_temps[~remove_temps.PartialSession.str.contains('Acting Representative', na=False)]
                                                # remove_temps should now have only one row
                                                district = remove_temps['District'].tolist()[0]

                        for i in vote_df.index:
                            if vote_df.loc[i, 'LastName'] in name and vote_df.loc[i, 'Chamber'] == 'House' and (district == None or (district != None and district == vote_df.loc[i, 'District'])):
                                # No dates
                                if vote_df.loc[i, 'StartDate'] == None and vote_df.loc[i, 'EndDate'] == None:
                                    vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]

                                # No more than one start/end date
                                elif (vote_df.loc[i, 'StartDate'] != None or vote_df.loc[i, 'EndDate'] != None) and vote_df.loc[i, 'StartDate2'] == None and vote_df.loc[i, 'EndDate2'] == None:
                                    if vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] == None:
                                        if vote_df.loc[i, 'StartDate'] <= house_vote_date:
                                                vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]
                                    elif vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate'] == None:
                                        if vote_df.loc[i, 'EndDate'] >= house_vote_date:
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]
                                    elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None:
                                        if vote_df.loc[i, 'StartDate'] >= vote_df.loc[i, 'EndDate'] and (house_vote_date >= vote_df.loc[i, 'StartDate'] or house_vote_date <= vote_df.loc[i, 'EndDate']):
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]
                                        elif vote_df.loc[i, 'StartDate'] <= vote_df.loc[i, 'EndDate'] and (vote_df.loc[i, 'StartDate'] <= house_vote_date <= vote_df.loc[i, 'EndDate']):
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]

                                # No more than two start/end dates
                                elif (vote_df.loc[i, 'StartDate2'] != None or vote_df.loc[i, 'EndDate2'] != None) and vote_df.loc[i, 'StartDate3'] == None and vote_df.loc[i, 'EndDate3'] == None:
                                    # Start date followed by temp absence (keep other scenario (startdate2 < enddate2) just in case)
                                    if vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] == None and vote_df.loc[i, 'StartDate2'] != None and vote_df.loc[i, 'EndDate2'] != None:
                                        if vote_df.loc[i, 'StartDate2'] >= vote_df.loc[i, 'EndDate2'] and (house_vote_date >= vote_df.loc[i, 'StartDate2'] or house_vote_date <= vote_df.loc[i, 'EndDate2']) and house_vote_date >= vote_df.loc[i, 'StartDate']:
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]
                                        elif vote_df.loc[i, 'StartDate2'] <= vote_df.loc[i, 'EndDate2'] and (vote_df.loc[i, 'StartDate2'] <= house_vote_date <= vote_df.loc[i, 'EndDate2']) and house_vote_date >= vote_df.loc[i, 'StartDate']:
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]

                                    # End date, but came back as sub for someone else (i.e. sd2 > ed2 not possible)
                                    elif vote_df.loc[i, 'StartDate'] == None and vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate2'] != None and vote_df.loc[i, 'EndDate2'] != None:
                                        if (vote_df.loc[i, 'StartDate2'] <= vote_df.loc[i, 'EndDate2'] and (vote_df.loc[i, 'StartDate2'] <= house_vote_date <= vote_df.loc[i, 'EndDate2'])) or house_vote_date <= vote_df.loc[i, 'EndDate']:
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]

                                    # Start and end plus start: sub and then permanent replacement (i.e. sd1 > ed1 not possible)
                                    elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate2'] != None and vote_df.loc[i, 'EndDate2'] == None:
                                        if (vote_df.loc[i, 'StartDate'] <= vote_df.loc[i, 'EndDate'] and (vote_df.loc[i, 'StartDate'] <= house_vote_date <= vote_df.loc[i, 'EndDate'])) or house_vote_date >= vote_df.loc[i, 'StartDate2']:
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]

                                    # Start and end plus end: temp absence and then end date (i.e. sd1 < ed1 not possible)
                                    elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate2'] == None and vote_df.loc[i, 'EndDate2'] != None:
                                        if (vote_df.loc[i, 'StartDate'] >= vote_df.loc[i, 'EndDate'] and (house_vote_date >= vote_df.loc[i, 'StartDate'] or house_vote_date <= vote_df.loc[i, 'EndDate'])) and house_vote_date <= vote_df.loc[i, 'EndDate2']:
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]

                                    # Two start and end dates; either two temp absences or two acting positions
                                    elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate2'] != None and vote_df.loc[i, 'EndDate2'] != None:
                                        # Two acting positions
                                        if vote_df.loc[i, 'StartDate'] <= vote_df.loc[i, 'EndDate'] and vote_df.loc[i, 'StartDate2'] <= vote_df.loc[i, 'EndDate2']:
                                            if (vote_df.loc[i, 'StartDate'] <= house_vote_date <= vote_df.loc[i, 'EndDate']) or (vote_df.loc[i, 'StartDate2'] <= house_vote_date <= vote_df.loc[i, 'EndDate2']):
                                                vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]
                                        # Two temp absences
                                        elif vote_df.loc[i, 'StartDate'] >= vote_df.loc[i, 'EndDate'] and vote_df.loc[i, 'StartDate2'] >= vote_df.loc[i, 'EndDate2']:
                                            if house_vote_date <= vote_df.loc[i, 'EndDate'] or (house_vote_date >= vote_df.loc[i, 'StartDate'] and house_vote_date <= vote_df.loc[i, 'EndDate2']) or house_vote_date >= vote_df.loc[i, 'StartDate2']:
                                                vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]

                                # Three start/end dates
                                elif vote_df.loc[i, 'StartDate3'] != None or vote_df.loc[i, 'EndDate3'] != None:
                                    # For now, assume either three temp absences or three acting positions; change later if needed
                                    # Three acting positions
                                    if vote_df.loc[i, 'StartDate'] <= vote_df.loc[i, 'EndDate'] and vote_df.loc[i, 'StartDate2'] <= vote_df.loc[i, 'EndDate2'] and vote_df.loc[i, 'StartDate3'] <= vote_df.loc[i, 'EndDate3']:
                                        if (vote_df.loc[i, 'StartDate'] <= house_vote_date <= vote_df.loc[i, 'EndDate']) or (vote_df.loc[i, 'StartDate2'] <= house_vote_date <= vote_df.loc[i, 'EndDate2']) or (vote_df.loc[i, 'StartDate3'] <= house_vote_date <= vote_df.loc[i, 'EndDate3']):
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]
                                    # Three temp absences
                                    elif vote_df.loc[i, 'StartDate'] >= vote_df.loc[i, 'EndDate'] and vote_df.loc[i, 'StartDate2'] >= vote_df.loc[i, 'EndDate2'] and vote_df.loc[i, 'StartDate3'] >= vote_df.loc[i, 'EndDate3']:
                                        if house_vote_date <= vote_df.loc[i, 'EndDate'] or (house_vote_date >= vote_df.loc[i, 'StartDate'] and house_vote_date <= vote_df.loc[i, 'EndDate2']) or (house_vote_date >= vote_df.loc[i, 'StartDate2'] and house_vote_date <= vote_df.loc[i, 'EndDate3']) or house_vote_date >= vote_df.loc[i, 'StartDate3']:
                                            vote_df.loc[i, f'{leg}'] = house_vote_dict[each_name]

                # Create dict of senate votes
                if senate_vote_date != None:
                    senate_text = bill_page_text.split(senate_vote_date2)[1:]
                    senate_text = " ".join(senate_text)
                    vote_type = (re.findall('(ayes|voice vote)', senate_text.lower()))[0]
                    if vote_type == 'voice vote' or (vote_type == 'ayes' and 'Abs/Excd' in senate_text and ("R" in leg or "P" in leg or "M" in leg)):
                        #vote_df.loc[vote_df.Chamber=="Senate", leg] = "Voice Vote - Passed"
                        senate_only = vote_df[vote_df.Chamber == 'Senate']
                        for i in senate_only.index:
                            senate_vote_dict[senate_only.loc[i, 'LastName']] = "Voice Vote - Passed"
                        district = None
                    else:
                        aye_index2 = senate_text.find("AYES")
                        nay_index2 = senate_text.find("NAY")
                        absent_index2 = senate_text.find("Absent")
                        excused_index2 = senate_text.find("Excused from voting")
                        floor_sponsor_index2 = senate_text.find("Floor ")
                        if floor_sponsor_index2 == -1 or floor_sponsor_index2 > absent_index2 + 300:
                            floor_sponsor_index2 = senate_text.find("Title ")
                        aye_list2 = (senate_text[aye_index2:nay_index2]).replace("AYES", "", 1).strip().strip('–').strip('--').strip().split(' ')
                        aye_list2 = list(map(lambda x: x.strip(',').strip().strip(","), aye_list2))
                        nay_list2 = (senate_text[nay_index2:absent_index2]).replace("NAYS", "", 1).strip().strip('–').strip('--').strip().split(' ')
                        nay_list2 = list(map(lambda x: x.strip(',').strip().strip(","), nay_list2))
                        if excused_index2 != -1:
                            absent_list2 = (senate_text[absent_index2:excused_index2]).replace("Absent and excused", "", 1).replace('Absent', "", 1).strip().strip('–').strip('--').strip().split(' ')
                            absent_list2 = list(map(lambda x: x.strip(',').strip().strip(","), absent_list2))
                            excused_list2 = (senate_text[excused_index2:floor_sponsor_index2]).replace("Excused from voting", "", 1).strip().strip('–').strip('--').strip().split(' ')
                            excused_list2 = list(map(lambda x: x.strip(',').strip().strip(","), excused_list2))
                        else:
                            absent_list2 = (senate_text[absent_index2:floor_sponsor_index2]).replace("Absent and excused", "", 1).replace('Absent', "", 1).strip().strip('–').strip('--').strip().split(' ')
                            absent_list2 = list(map(lambda x: x.strip(',').strip().strip(","), absent_list2))
                            excused_list2 = []
                        aye_list2 = [x for x in aye_list2 if x != "None" and x != ""]
                        nay_list2 = [x for x in nay_list2 if x != "None" and x != ""]
                        absent_list2 = [x for x in absent_list2 if x != "None" and x != ""]
                        excused_list2 = [x for x in excused_list2 if x != "None" and x != ""]

                        # If both votes are on the same day, check the number of names to make sure house is house and sen is sen
                        # Use 55 as threshold
                        while len(aye_list2) + len(nay_list2) + len(absent_list2) + len(excused_list2) > 55:
                            senate_text = senate_text[floor_sponsor_index2+5:]
                            aye_index2 = senate_text.find("AYES")
                            nay_index2 = senate_text.find("NAY")
                            absent_index2 = senate_text.find("Absent")
                            excused_index2 = senate_text.find("Excused from voting")
                            floor_sponsor_index2 = senate_text.find("Floor ")
                            if floor_sponsor_index2 == -1 or floor_sponsor_index2 > absent_index2 + 300:
                                floor_sponsor_index2 = senate_text.find("Title ")
                            aye_list2 = (senate_text[aye_index2:nay_index2]).replace("AYES", "", 1).strip().strip('–').strip('--').strip().split(' ')
                            aye_list2 = list(map(lambda x: x.strip(',').strip().strip(","), aye_list2))
                            nay_list2 = (senate_text[nay_index2:absent_index2]).replace("NAYS", "", 1).strip().strip('–').strip('--').strip().split(' ')
                            nay_list2 = list(map(lambda x: x.strip(',').strip().strip(","), nay_list2))
                            if excused_index2 != -1:
                                absent_list2 = (senate_text[absent_index2:excused_index2]).replace("Absent and excused", "", 1).replace('Absent', "", 1).strip().strip('–').strip('--').strip().split(' ')
                                absent_list2 = list(map(lambda x: x.strip(',').strip().strip(","), absent_list2))
                                excused_list2 = (senate_text[excused_index2:floor_sponsor_index2]).replace("Excused from voting", "", 1).strip().strip('–').strip('--').strip().split(' ')
                                excused_list2 = list(map(lambda x: x.strip(',').strip().strip(","), excused_list2))
                            else:
                                absent_list2 = (senate_text[absent_index2:floor_sponsor_index2]).replace("Absent and excused", "", 1).replace('Absent', "", 1).strip().strip('–').strip('--').strip().split(' ')
                                absent_list2 = list(map(lambda x: x.strip(',').strip().strip(","), absent_list2))
                                excused_list2 = []
                            aye_list2 = [x for x in aye_list2 if x != "None" and x != ""]
                            nay_list2 = [x for x in nay_list2 if x != "None" and x != ""]
                            absent_list2 = [x for x in absent_list2 if x != "None" and x != ""]
                            excused_list2 = [x for x in excused_list2 if x != "None" and x != ""]

                        for name in aye_list2:
                            senate_vote_dict[name] = "Aye"
                        for name in nay_list2:
                            senate_vote_dict[name] = "Nay"
                        for name in absent_list2:
                            senate_vote_dict[name] = "Absent"
                        for name in excused_list2:
                            senate_vote_dict[name] = "Excused from voting"

                        commas = []
                        for key in senate_vote_dict.keys():
                            if "," in key:
                                commas.append(key)

                        for comma in commas:
                            pt1 = comma.split(",")[0]
                            pt2 = comma.split(",")[1]
                            senate_vote_dict[pt1] = senate_vote_dict[comma]
                            senate_vote_dict[pt2] = senate_vote_dict.pop(comma)

                    # Fix chronic misspellings on website
                    # 1998
                    new_key = None
                    if "Diede" in list(senate_vote_dict.keys()):
                        senate_vote_dict['Deide'] = senate_vote_dict.pop('Diede')
                    else:
                        for key in senate_vote_dict:
                            if "Diede" in key:
                                old_key = key
                                new_key = key.replace("Diede", "Deide")
                        if new_key !=None:
                            senate_vote_dict[new_key] = senate_vote_dict.pop(old_key)

                    # Add votes to vote_df
                    for each_name in senate_vote_dict:
                        name = each_name

                        if "Voice Vote - Passed" not in senate_vote_dict.values():
                            # Split by parenthesis to create list of names to avoid partial string matching (e.g. Field in Fields)
                            name = name.split("(")
                            name = list(map(lambda x: x.strip("() ,"), name))
                            name = [x for x in name if x != ""]

                            district = None
                            if any(item in s_dup_names['LastName'].tolist() for item in name):
                                try:
                                    for d in name:
                                        if all(map(str.isdigit, d)):
                                            district = d
                                    district = int(district)
                                except:
                                    for item in name:
                                        if item in s_dup_names['LastName'].tolist():
                                            final_name = item

                                    dup_name_only = s_dup_names[s_dup_names.LastName == final_name]

                                    if len(dup_name_only['District'].unique())==1:
                                        district = dup_name_only['District'].unique()[0]

                                    else:
                                        dist_nums = s_dup_names[s_dup_names.LastName == final_name]
                                        dist_nums = dist_nums['District'].tolist()
                                        all_names = list(senate_vote_dict.keys())
                                        all_names = [x for x in all_names if final_name in x]
                                        all_names = [x for x in all_names if any(map(str.isdigit, x))]
                                        all_names = list(map(lambda x: ''.join(re.findall('\d+', x)), all_names))
                                        all_names = list(map(lambda x: int(x), all_names))
                                        missing_dist = [x for x in dist_nums if x not in all_names]


                                        # If none of the duplicate last names are temp legislators
                                        if (all('Acting Senator' not in x for x in dup_name_only['PartialSession'].tolist()) and all("Acting Representative" not in x for x in dup_name_only['PartialSession'].tolist()) and all('Temporary Absence' not in x for x in dup_name_only['PartialSession'].tolist())) or len(missing_dist)==1:
                                            district = missing_dist[0]

                                        # If some of the duplicate last names are temp legislators
                                        elif (any('Acting Senator' in x for x in dup_name_only['PartialSession'].tolist()) or any("Acting Representative" in x for x in dup_name_only['PartialSession'].tolist()) or any('Temporary Absence' in x for x in dup_name_only['PartialSession'].tolist())) and len(missing_dist) > 1:
                                            all_names2 = list(senate_vote_dict.keys())
                                            all_names2 = [x for x in all_names2 if final_name in x]
                                            all_names2 = [x for x in all_names2 if not any(map(str.isdigit, x))]

                                            if "(" in each_name:
                                                #try:
                                                all_names2.remove(final_name)
                                                for name1 in all_names2:
                                                    ind_name = name1.split("(")
                                                    ind_name = list(map(lambda x: x.strip("() ,"), name))
                                                    ind_name = [x for x in name if x != ""]
                                                    # (Note: length of ind_name should never exceed 2)
                                                    dist_nums1 = dup_names[dup_names.Chamber == 'Senate']
                                                    dist_nums1 = dist_nums1[dist_nums1.LastName == ind_name[0]]
                                                    dist_nums1 = dist_nums1['District'].tolist()
                                                    dist_nums2 = dup_names[dup_names.Chamber == 'Senate']
                                                    dist_nums2 = dist_nums2[dist_nums2.LastName == ind_name[1]]
                                                    dist_nums2 = dist_nums2['District'].tolist()

                                                    match = [x for x in dist_nums1 if x in dist_nums2]

                                                    district = match[0]
                                                #except:
                                                    #logging.info(f'ERROR: Unable to detect correct district for {each_name}.')

                                            else:
                                                remove_temps = s_dup_names[s_dup_names.LastName == final_name]
                                                remove_temps = remove_temps[~remove_temps.PartialSession.str.contains('Acting Senator', na=False)]
                                                # remove_temps should now have only one row
                                                district = remove_temps['District'].tolist()[0]

                        for i in vote_df.index:
                            if vote_df.loc[i, 'LastName'] in name and vote_df.loc[i, 'Chamber'] == 'Senate' and (district == None or (district != None and district == vote_df.loc[i, 'District'])):
                                # No dates
                                if vote_df.loc[i, 'StartDate'] == None and vote_df.loc[i, 'EndDate'] == None:
                                    vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]

                                # No more than one start/end date
                                elif (vote_df.loc[i, 'StartDate'] != None or vote_df.loc[i, 'EndDate'] != None) and vote_df.loc[i, 'StartDate2'] == None and vote_df.loc[i, 'EndDate2'] == None:
                                    if vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] == None:
                                        if vote_df.loc[i, 'StartDate'] <= senate_vote_date:
                                                vote_df.loc[i, f'{leg}'] =senate_vote_dict[each_name]
                                    elif vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate'] == None:
                                        if vote_df.loc[i, 'EndDate'] >= senate_vote_date:
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]
                                    elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None:
                                        if vote_df.loc[i, 'StartDate'] >= vote_df.loc[i, 'EndDate'] and (senate_vote_date >= vote_df.loc[i, 'StartDate'] or senate_vote_date <= vote_df.loc[i, 'EndDate']):
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]
                                        elif vote_df.loc[i, 'StartDate'] <= vote_df.loc[i, 'EndDate'] and (vote_df.loc[i, 'StartDate'] <= senate_vote_date <= vote_df.loc[i, 'EndDate']):
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]

                                # No more than two start/end dates
                                elif (vote_df.loc[i, 'StartDate2'] != None or vote_df.loc[i, 'EndDate2'] != None) and vote_df.loc[i, 'StartDate3'] == None and vote_df.loc[i, 'EndDate3'] == None:
                                    # Start date followed by temp absence (keep other scenario (startdate2 < enddate2) just in case)
                                    if vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] == None and vote_df.loc[i, 'StartDate2'] != None and vote_df.loc[i, 'EndDate2'] != None:
                                        if vote_df.loc[i, 'StartDate2'] >= vote_df.loc[i, 'EndDate2'] and (senate_vote_date >= vote_df.loc[i, 'StartDate2'] or senate_vote_date <= vote_df.loc[i, 'EndDate2']) and senate_vote_date >= vote_df.loc[i, 'StartDate']:
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]
                                        elif vote_df.loc[i, 'StartDate2'] <= vote_df.loc[i, 'EndDate2'] and (vote_df.loc[i, 'StartDate2'] <= senate_vote_date <= vote_df.loc[i, 'EndDate2']) and senate_vote_date >= vote_df.loc[i, 'StartDate']:
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]

                                    # End date, but came back as sub for someone else (i.e. sd2 > ed2 not possible)
                                    elif vote_df.loc[i, 'StartDate'] == None and vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate2'] != None and vote_df.loc[i, 'EndDate2'] != None:
                                        if (vote_df.loc[i, 'StartDate2'] <= vote_df.loc[i, 'EndDate2'] and (vote_df.loc[i, 'StartDate2'] <= senate_vote_date <= vote_df.loc[i, 'EndDate2'])) or senate_vote_date <= vote_df.loc[i, 'EndDate']:
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]

                                    # Start and end plus start: sub and then permanent replacement (i.e. sd1 > ed1 not possible)
                                    elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate2'] != None and vote_df.loc[i, 'EndDate2'] == None:
                                        if (vote_df.loc[i, 'StartDate'] <= vote_df.loc[i, 'EndDate'] and (vote_df.loc[i, 'StartDate'] <= senate_vote_date <= vote_df.loc[i, 'EndDate'])) or senate_vote_date >= vote_df.loc[i, 'StartDate2']:
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]

                                    # Start and end plus end: temp absence and then end date (i.e. sd1 < ed1 not possible)
                                    elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate2'] == None and vote_df.loc[i, 'EndDate2'] != None:
                                        if (vote_df.loc[i, 'StartDate'] >= vote_df.loc[i, 'EndDate'] and (senate_vote_date >= vote_df.loc[i, 'StartDate'] or senate_vote_date <= vote_df.loc[i, 'EndDate'])) and senate_vote_date <= vote_df.loc[i, 'EndDate2']:
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]

                                    # Two start and end dates; either two temp absences or two acting positions
                                    elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate2'] != None and vote_df.loc[i, 'EndDate2'] != None:
                                        # Two acting positions
                                        if vote_df.loc[i, 'StartDate'] <= vote_df.loc[i, 'EndDate'] and vote_df.loc[i, 'StartDate2'] <= vote_df.loc[i, 'EndDate2']:
                                            if (vote_df.loc[i, 'StartDate'] <= senate_vote_date <= vote_df.loc[i, 'EndDate']) or (vote_df.loc[i, 'StartDate2'] <= senate_vote_date <= vote_df.loc[i, 'EndDate2']):
                                                vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]
                                        # Two temp absences
                                        elif vote_df.loc[i, 'StartDate'] >= vote_df.loc[i, 'EndDate'] and vote_df.loc[i, 'StartDate2'] >= vote_df.loc[i, 'EndDate2']:
                                            if senate_vote_date <= vote_df.loc[i, 'EndDate'] or (senate_vote_date >= vote_df.loc[i, 'StartDate'] and senate_vote_date <= vote_df.loc[i, 'EndDate2']) or senate_vote_date >= vote_df.loc[i, 'StartDate2']:
                                                vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]

                                # Three start/end dates
                                elif vote_df.loc[i, 'StartDate3'] != None or vote_df.loc[i, 'EndDate3'] != None:
                                    # For now, assume either three temp absences or three acting positions; change later if needed
                                    # Three acting positions
                                    if vote_df.loc[i, 'StartDate'] <= vote_df.loc[i, 'EndDate'] and vote_df.loc[i, 'StartDate2'] <= vote_df.loc[i, 'EndDate2'] and vote_df.loc[i, 'StartDate3'] <= vote_df.loc[i, 'EndDate3']:
                                        if (vote_df.loc[i, 'StartDate'] <= senate_vote_date <= vote_df.loc[i, 'EndDate']) or (vote_df.loc[i, 'StartDate2'] <= senate_vote_date <= vote_df.loc[i, 'EndDate2']) or (vote_df.loc[i, 'StartDate3'] <= senate_vote_date <= vote_df.loc[i, 'EndDate3']):
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]
                                    # Three temp absences
                                    elif vote_df.loc[i, 'StartDate'] >= vote_df.loc[i, 'EndDate'] and vote_df.loc[i, 'StartDate2'] >= vote_df.loc[i, 'EndDate2'] and vote_df.loc[i, 'StartDate3'] >= vote_df.loc[i, 'EndDate3']:
                                        if senate_vote_date <= vote_df.loc[i, 'EndDate'] or (senate_vote_date >= vote_df.loc[i, 'StartDate'] and senate_vote_date <= vote_df.loc[i, 'EndDate2']) or (senate_vote_date >= vote_df.loc[i, 'StartDate2'] and senate_vote_date <= vote_df.loc[i, 'EndDate3']) or senate_vote_date >= vote_df.loc[i, 'StartDate3']:
                                            vote_df.loc[i, f'{leg}'] = senate_vote_dict[each_name]

            if len(house_vote_dict) == 0:
                vote_df.loc[vote_df.Chamber == 'House', leg] = ''

            if len(senate_vote_dict) == 0:
                vote_df.loc[vote_df.Chamber == 'Senate', leg] = ''

            logging.info(f'{leg}: Vote scraping successful')

        else:
            vote_df[leg] = "404"

    # Remove last name column
    vote_df.drop(columns='LastName', inplace=True)

    return vote_df

def main():
    # Configure logging module
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)

    # Log DEBUG level to file
    fh = logging.FileHandler('vote_scraping.log', 'w')
    fh.setLevel(logging.DEBUG)
    rootLogger.addHandler(fh)

    # Print INFO level to console
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    rootLogger.addHandler(sh)


    # Use argparse to parse command-line arguments
    parser = argparse.ArgumentParser(description = "Web scrape Idaho legislature vote data")

    # Add positional argument to select year
    parser.add_argument('year', metavar='<year>', help='Selects legislative session year', choices=['1998', '1999', '2000', '2001', '2002', '2003', '2004', '2005', '2006', '2007', '2008', '2009', '2010', '2011', '2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019', '2020'])

    args = parser.parse_args()
    year = args.year

    full_leg_list = get_leg(year)
    final_vote_df = create_df(full_leg_list, year)
    with pd.ExcelWriter('vote_counts/all_vote_counts.xlsx', mode='a', datetime_format='yyyy-mm-dd', date_format='yyyy-mm-dd') as writer:
        final_vote_df.to_excel(writer, sheet_name=f'{year}', index=False)


if __name__ == "__main__":
    main()
