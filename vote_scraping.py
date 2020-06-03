import requests
from bs4 import BeautifulSoup
import re
import csv
from collections import defaultdict
import pandas as pd
import os
import argparse
import numpy as np
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

def get_vote_type(leg_list, year):
    vote_type_dict = {}
    bill_page_dict = {}

    for leg in leg_list:
        vote_page = requests.get(f'https://legislature.idaho.gov/sessioninfo/{year}/legislation/{str(leg)}/')

        if vote_page.status_code != 404:

            soup = BeautifulSoup(vote_page.content, "html.parser")

            vote_type = ""

            if int(year) < 2009:
                bill_page_text = (soup.find_all("pre"))[0]
            else:
                bill_page_text = soup.find_all("tr")
                bill_page_text = " ".join(bill_page_text)

            if "voice vote".casefold() in str(bill_page_text).casefold():
                vote_type = "Voice Vote"
            elif "Ayes".casefold() in str(bill_page_text).casefold() and "voice vote".casefold() not in str(bill_page_text).casefold():
                vote_type = "Formal"
            else:
                vote_type = "None"

        else:
            bill_page_text = "404"
            vote_type = "404"

        vote_type_dict[leg] = vote_type
        bill_page_dict[leg] = bill_page_text

    for leg in leg_list:
        if bill_page_dict[leg] == "404":
            del bill_page_dict[leg]

    return vote_type_dict, bill_page_dict


def create_df(vote_type_dict, bill_page_dict, year):
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



    # Enter votes for each piece of legislation
    for leg in vote_type_dict:
        if vote_type_dict[leg] == "Voice Vote":
            vote_df[leg] = "Voice Vote"
        elif vote_type_dict[leg] == "404" or vote_type_dict[leg] == "None":
            vote_df[leg] = ""
        elif vote_type_dict[leg] == "Formal":
            page_text = str(bill_page_dict[leg])

            try:
                house_vote_date = date.fromisoformat(str(bill_df.loc[leg, 'house_vote_date']))
            except:
                house_vote_date = None
            try:
                senate_vote_date = date.fromisoformat(str(bill_df.loc[leg, 'senate_vote_date']))
            except:
                senate_vote_date = None

            aye_count = re.findall(r'A[Y|y][E|e][S|s]', page_text)

            aye_index2 = page_text.rfind("AYES")
            nay_index2 = page_text.rfind("NAYS")
            absent_index2 = page_text.rfind("Absent")
            floor_sponsor_index2 = page_text.rfind("Floor ")
            aye_list2 = (page_text[aye_index2:nay_index2]).strip("AYES").strip().strip('–').strip('--').strip().split(' ')
            aye_list2 = list(map(lambda x: x.strip(',').strip(), aye_list2))
            nay_list2 = (page_text[nay_index2:absent_index2]).strip("NAYS").strip().strip('–').strip('--').strip().split(' ')
            nay_list2 = list(map(lambda x: x.strip(',').strip(), nay_list2))
            absent_list2 = (page_text[absent_index2:floor_sponsor_index2]).strip("Absent and excused").strip('Absent').strip().strip('–').strip('--').strip().split(' ')
            absent_list2 = list(map(lambda x: x.strip(',').strip(), absent_list2))
            vote_dict2 = {}
            for name in aye_list2:
                vote_dict2[name] = "Aye"
            for name in nay_list2:
                vote_dict2[name] = "Nay"
            for name in absent_list2:
                vote_dict2[name] = "Absent"

            vote_dict1 = False
            if len(aye_count) > 1:
                page_text = page_text[0:aye_index2]
                aye_index1 = page_text.rfind("AYES")
                nay_index1 = page_text.rfind("NAYS")
                absent_index1 = page_text.rfind("Absent")
                floor_sponsor_index1 = page_text.rfind("Floor ")
                aye_list1 = (page_text[aye_index1:nay_index1]).strip("AYES").strip().strip('–').strip('--').strip().split(' ')
                aye_list1 = list(map(lambda x: x.strip(',').strip(), aye_list1))
                nay_list1 = (page_text[nay_index1:absent_index1]).strip("NAYS").strip().strip('–').strip('--').strip().split(' ')
                nay_list1 = list(map(lambda x: x.strip(',').strip(), nay_list1))
                absent_list1 = (page_text[absent_index1:floor_sponsor_index1]).strip("Absent and excused").strip('Absent').strip().strip('–').strip('--').strip().split(' ')
                absent_list1 = list(map(lambda x: x.strip(',').strip(), absent_list1))
                vote_dict1 = {}
                for name in aye_list1:
                    vote_dict1[name] = "Aye"
                for name in nay_list1:
                    vote_dict1[name] = "Nay"
                for name in absent_list1:
                    vote_dict1[name] = "Absent"

            # If vote_dict2 has more than 35 names, it's a House vote. Evaluating if it has more than 40 names just to make sure that errors on the website don't throw this off.
            if len(vote_dict2) > 40:
                dict2_house = True
            else:
                dict2_house = False


            if vote_dict1 != False:
                if len(vote_dict1) > 40:
                    dict1_house = True
                else:
                    dict1_house = False
                for name in vote_dict1:
                    district = None
                    if name.endswith(')') == True:
                        district = name.split('(')[1].strip(')')
                        try:
                            district = int(district)
                        except:
                            district = None
                    if dict1_house == True:
                        for i in vote_df.index:
                            if vote_df.loc[i, 'LastName'] in name and vote_df.loc[i, 'Chamber'] == 'House' and (district == None or (district != None and district == vote_df.loc[i, 'District'])):
                                if vote_df.loc[i, 'StartDate'] == None and vote_df.loc[i, 'EndDate'] == None:
                                    vote_df.loc[i, f'{leg}'] = vote_dict1[name]
                                elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] == None:
                                    if vote_df.loc[i, 'StartDate'] < house_vote_date:
                                        vote_df.loc[i, f'{leg}'] = vote_dict1[name]
                                elif vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate'] == None:
                                    if vote_df.loc[i, 'EndDate'] > house_vote_date:
                                        vote_df.loc[i, f'{leg}'] = vote_dict1[name]
                                elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None:
                                    if vote_df.loc[i, 'StartDate'] < house_vote_date < vote_df.loc[i, 'EndDate']:
                                        vote_df.loc[i, f'{leg}'] = vote_dict1[name]

                    if dict1_house == False:
                        for i in vote_df.index:
                            if vote_df.loc[i, 'LastName'] in name and vote_df.loc[i, 'Chamber'] == 'Senate' and (district == None or (district != None and district == vote_df.loc[i, 'District'])):
                                if vote_df.loc[i, 'StartDate'] == None and vote_df.loc[i, 'EndDate'] == None:
                                    vote_df.loc[i, f'{leg}'] = vote_dict1[name]
                                elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] == None:
                                    if vote_df.loc[i, 'StartDate'] < senate_vote_date:
                                        vote_df.loc[i, f'{leg}'] = vote_dict1[name]
                                elif vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate'] == None:
                                    if vote_df.loc[i, 'EndDate'] > senate_vote_date:
                                        vote_df.loc[i, f'{leg}'] = vote_dict1[name]
                                elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None:
                                    if vote_df.loc[i, 'StartDate'] < senate_vote_date < vote_df.loc[i, 'EndDate']:
                                        vote_df.loc[i, f'{leg}'] = vote_dict1[name]

            for name in vote_dict2:
                district = None
                if name.endswith(')') == True:
                    district = name.split('(')[1].strip(')')
                    try:
                        district = int(district)
                    except:
                        district = None
                if dict2_house == False:
                    for i in vote_df.index:
                        if vote_df.loc[i, 'LastName'] in name and vote_df.loc[i, 'Chamber'] == 'Senate' and (district == None or (district != None and district == vote_df.loc[i, 'District'])):
                            if vote_df.loc[i, 'StartDate'] == None and vote_df.loc[i, 'EndDate'] == None:
                                vote_df.loc[i, f'{leg}'] = vote_dict2[name]
                            elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] == None:
                                if vote_df.loc[i, 'StartDate'] < senate_vote_date:
                                    vote_df.loc[i, f'{leg}'] = vote_dict2[name]
                            elif vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate'] == None:
                                if vote_df.loc[i, 'EndDate'] > senate_vote_date:
                                    vote_df.loc[i, f'{leg}'] = vote_dict2[name]
                            elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None:
                                if vote_df.loc[i, 'StartDate'] < senate_vote_date < vote_df.loc[i, 'EndDate']:
                                    vote_df.loc[i, f'{leg}'] = vote_dict2[name]

                if dict2_house == True:
                    for i in vote_df.index:
                        if vote_df.loc[i, 'LastName'] in name and vote_df.loc[i, 'Chamber'] == 'House' and (district == None or (district != None and district == vote_df.loc[i, 'District'])):
                            if vote_df.loc[i, 'StartDate'] == None and vote_df.loc[i, 'EndDate'] == None:
                                vote_df.loc[i, f'{leg}'] = vote_dict2[name]
                            if vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] == None:
                                if vote_df.loc[i, 'StartDate'] < house_vote_date:
                                    vote_df.loc[i, f'{leg}'] = vote_dict2[name]
                            elif vote_df.loc[i, 'EndDate'] != None and vote_df.loc[i, 'StartDate'] == None:
                                if vote_df.loc[i, 'EndDate'] > house_vote_date:
                                    vote_df.loc[i, f'{leg}'] = vote_dict2[name]
                            elif vote_df.loc[i, 'StartDate'] != None and vote_df.loc[i, 'EndDate'] != None:
                                if vote_df.loc[i, 'StartDate'] < house_vote_date < vote_df.loc[i, 'EndDate']:
                                    vote_df.loc[i, f'{leg}'] = vote_dict2[name]

        logging.info(f'{leg}: Vote scraping successful')

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
    #full_leg_list = ["H0001", "H0002", "H0322", "HCR001", "S1218"]
    vote_type_dict, bill_page_dict = get_vote_type(full_leg_list, year)
    final_vote_df = create_df(vote_type_dict, bill_page_dict, year)
    with pd.ExcelWriter('vote_counts/all_vote_counts.xlsx', mode='a') as writer:
        final_vote_df.to_excel(writer, sheet_name=f'{year}', index=False)


if __name__ == "__main__":
    main()
