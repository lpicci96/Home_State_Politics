# Program scrapes legislation-related data from Idaho State Legislature website and creates a csv file

# Import necessary packages
import vote_scraping
import requests
from bs4 import BeautifulSoup
import re
import csv
import argparse
import PyPDF2
import urllib.request
import pandas as pd
import logging
from datetime import date
import pikepdf

# Configure logging module
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.DEBUG)

# Log DEBUG level to file
fh = logging.FileHandler('bill_info_scraper.log', 'w')
fh.setLevel(logging.DEBUG)
rootLogger.addHandler(fh)

# Print INFO level to console
sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
rootLogger.addHandler(sh)


# Get info for bills after 2008; website/html format changed between 2008 and 2009
def get_info_post09(leg_list, year, leg_info_df):

    for leg in leg_list:
        link = f'https://legislature.idaho.gov/sessioninfo/{year}/legislation/{str(leg)}/'
        vote_page = requests.get(link)

        # Get short outcome
        mini_data = requests.get(f'https://legislature.idaho.gov/sessioninfo/{year}/legislation/')
        mini_data_soup = BeautifulSoup(mini_data.content, 'html.parser')
        short_outcome = mini_data_soup.find_all(id = f'bill{leg}')
        if len(short_outcome) == 0:
            short_outcome = mini_data_soup.find_all(id = f'bill{leg}a')
        short_outcome = ((short_outcome[0]).find_all('td'))[3].text

        if vote_page.status_code != 404:

            soup = BeautifulSoup(vote_page.content, "html.parser")

            # Get description
            desc_soup = soup.find_all(class_="bill-table")
            desc = desc_soup[1].text
            desc = (''.join(desc.split('\n')))
            desc = desc.replace('–', '-')
            desc = desc.replace('“', '"')
            desc = desc.replace('”', '"')
            desc = desc.strip()


            # Get long outcome
            outcome_soup = soup.find_all(class_="bill-table")
            outcome = ((outcome_soup[2].find_all('tr'))[-1]).text
            nbs = u'\xa0'
            outcome = outcome.replace(nbs, " ")
            outcome = outcome.replace('–', "-")
            outcome = (''.join(outcome.split('\n')))
            outcome = ((outcome.replace('    ', '; ')).strip()).strip('; ')
            if str(year) in outcome:
                outcome = outcome.lstrip('0123456789/; ')
            if "AYES" in outcome:
                outcome = (outcome.split('AYES'))[0]


            # Get governor's action
            gov_action = ""
            if "law" in short_outcome.lower() or "veto" in short_outcome.lower():
                if "sign" in outcome.lower() and 'without' not in outcome.lower():
                    gov_action = 'Signed'
                elif "veto" in short_outcome.lower() and "line item" not in short_outcome.lower():
                    gov_action = 'Vetoed'
                elif "line item veto" in short_outcome.lower():
                    gov_action = 'Line Item Veto'
                elif 'without' in outcome.lower() and "veto" not in outcome.lower() and ("effective" in outcome.lower() or "law" in outcome.lower()):
                    gov_action = 'Passed without signature'


            # Get legislative co-sponsors
            sponsor_soup = soup.find_all('a', id=f'{leg}LegCo')
            sponsor_list = []
            if len(sponsor_soup) == 1:
                sponsor_link = sponsor_soup[0].get('href')
                check_404 = requests.get(f'https://legislature.idaho.gov{sponsor_link}')
                if check_404.status_code != 404:
                    sponsor_pdf, headers = urllib.request.urlretrieve(f'https://legislature.idaho.gov{sponsor_link}', f'{leg}_cosponsors.pdf')
                    with pikepdf.open(f'{leg}_cosponsors.pdf') as encrypted:
                        encrypted.save(f'{leg}_cosponsors2.pdf')
                    with open(f'{leg}_cosponsors2.pdf', 'rb') as f:
                        sponsor_content = PyPDF2.PdfFileReader(f)
                        if sponsor_content.isEncrypted:
                                sponsor_content.decrypt("")
                        pageObj = sponsor_content.getPage(0)
                        sponsor_text = pageObj.extractText()
                        reps = re.findall(r'Representative [A-Z][a-z]* [A-Z][a-z]*', sponsor_text)
                        sens = re.findall(r'Senator [A-Z][a-z]* [A-Z][a-z]*', sponsor_text)
                    for rep in reps:
                        sponsor_list.append(rep)
                    for sen in sens:
                        sponsor_list.append(sen)
                else:
                    sponsor_list = ''
            else:
                sponsor_list = ''


            # Get floor sponsors
            floor_sponsor_page = ((soup.find_all(class_="bill-table"))[2]).text
            floor_sponsor_page = floor_sponsor_page.replace('\xa0', ' ')
            floor_sponsors = re.findall(r'Floor Sponsor.*Title', floor_sponsor_page)
            fs_list = []
            count = 1
            for sponsor in floor_sponsors:
                if count < 3:
                    sponsor = sponsor.strip('Floor Sponsor')
                    sponsor = sponsor.strip('–')
                    sponsor = sponsor.strip('-')
                    sponsor = sponsor.replace('Title', '')
                    split = False
                    if "," in sponsor and "&" in sponsor:
                        sponsor = re.split(',|&', sponsor)
                        split = True
                    elif "&" in sponsor and "," not in sponsor:
                        sponsor = sponsor.split('&')
                        split = True
                    elif "," in sponsor and "&" not in sponsor:
                        sponsor = sponsor.split(',')
                        split = True
                    if split == True:
                        for person in sponsor:
                            person = person.strip()
                            person = person.strip('& ')
                            if count == 1:
                                if leg.startswith('H')==True and person.startswith('Speaker') == False and person.startswith('Mr.') == False:
                                    person = f'Representative {person}'
                                elif leg.startswith('S')==True and person.startswith('President') == False:
                                    person = f'Senator {person}'
                            elif count == 2:
                                if leg.startswith('H')==True and person.startswith('President') == False:
                                    person = f'Senator {person}'
                                elif leg.startswith('S')==True and person.startswith('Speaker') == False and person.startswith('Mr.') == False:
                                    person = f'Representative {person}'
                            fs_list.append(person)
                    else:
                        sponsor = sponsor.strip()
                        if count == 1:
                            if leg.startswith('H')==True and sponsor.startswith('Speaker') == False and sponsor.startswith('Mr.') == False:
                                sponsor = f'Representative {sponsor}'
                            elif leg.startswith('S')==True and sponsor.startswith('President') == False:
                                sponsor = f'Senator {sponsor}'
                        elif count == 2:
                            if leg.startswith('H')==True and sponsor.startswith('President') == False:
                                sponsor = f'Senator {sponsor}'
                            elif leg.startswith('S')==True and sponsor.startswith('Speaker') == False and sponsor.startswith('Mr.') == False:
                                sponsor = f'Representative {sponsor}'
                        fs_list.append(sponsor)
                count+=1
            length = len(fs_list)
            if length == 0:
                fs_list = ''


            # Get vote dates
            dates = (soup.find_all(class_="bill-table"))[2].text
            dates = dates.replace(u'\xa0', " ").replace('\n', ' ').upper()
            find_chambers = dates.replace('ADOPTED', 'SPLIT_POINT').replace('FAILED', 'SPLIT_POINT').replace('PASSED', 'SPLIT_POINT')
            date_dict = {'house': '', 'senate': ''}
            try:
                find_chambers = find_chambers.split('SPLIT_POINT')[1:]
            except:
                find_chambers = None
            if find_chambers != None:
                housedate = None
                senatedate = None
                count=0
                for x in find_chambers:
                    if "VOICE VOTE" in x:
                        if (count % 2 == 0 and leg.startswith("S") == True) or (count % 2 == 1 and leg.startswith("H")==True):
                            senatedate = count
                        elif (count % 2 == 0 and leg.startswith("H") == True) or (count % 2 == 1 and leg.startswith("S")==True):
                            housedate = count
                    elif "AYES" in x or "NAYS" in x:
                        num_voters = re.findall(r'[0-9][0-9]? ?--? ?[0-9][0-9]? ?--? ?[0-9][0-9]?', x)
                        num_voters = num_voters[0].split('-')
                        num_voters = list(map(lambda x: int(x), num_voters))
                        num_voters = sum(num_voters[0:])
                        # Use 60 and 40 as cutoffs to account for minor errors in the count
                        if num_voters > 60:
                            housedate = count
                        elif num_voters < 40:
                            senatedate = count
                    count+=1

                # Get house vote date
                if housedate != None:
                    house_vote_text = dates.split(find_chambers[housedate])[0]
                    house_vote_date = re.findall(r'[0-9][0-9]/[0-9][0-9]', house_vote_text)[-1]
                    hmonth = int(house_vote_date.split('/')[0].strip())
                    hday = int(house_vote_date.split('/')[1].split(' ')[0])
                    date_dict['house'] = date(year, hmonth, hday)

                # Get senate vote date
                if senatedate != None:
                    senate_vote_text = dates.split(find_chambers[senatedate])[0]
                    senate_vote_date = re.findall(r'[0-9][0-9]/[0-9][0-9]', senate_vote_text)[-1]
                    smonth = int(senate_vote_date.split('/')[0].strip())
                    sday = int(senate_vote_date.split('/')[1].split(' ')[0])
                    date_dict['senate'] = date(year, smonth, sday)


            # Determine if amended
            amended_info = soup.find_all('a', string=re.compile('.*Amendment.*'))
            if len(amended_info) > 0:
                amended = "Amended"
            else:
                amended = ''

            # No notes
            notes = ''

        # Create variables if 404
        else:
            logging.info(f'{leg}: 404 Error')
            amended = ''
            outcome = ''
            sponsor_list = ''
            fs_list = ''
            gov_action = ''
            desc = ''
            date_dict = {'house':'', 'senate':''}
            # 404 note
            notes = '404 Error'


        # Create dataframe row
        df_row = {"bill_num": leg, "amended": amended, "short_outcome": short_outcome, "final_action": outcome, "house_vote_date": date_dict['house'], "senate_vote_date": date_dict['senate'], "leg_cosponsors": sponsor_list, "floor_sponsors": fs_list, "gov_action": gov_action, "short_desc": desc, "long_desc": '', "topics_all": '', "topics_coded": '', "t1": '', "t1_aye": '', "t2": '', "t2_aye": '', "t3": '', "t3_aye": '', "t4": '', "t4_aye": '', "t5": '', "t5_aye": '', "bill_group": '', "link": link, "notes": notes}

        leg_info_df = leg_info_df.append(df_row, ignore_index=True)
        logging.info(f'{leg}: Scraping successful')

    return leg_info_df


# Get info for bills before 2009; website/html format changed between 2008 and 2009
def get_info_pre09(leg_list, year, leg_info_df):

    for leg in leg_list:
        link = f'https://legislature.idaho.gov/sessioninfo/{year}/legislation/{str(leg)}/'
        vote_page = requests.get(link)

        # Get short outcome
        mini_data = requests.get(f'https://legislature.idaho.gov/sessioninfo/{year}/legislation/')
        mini_data_soup = BeautifulSoup(mini_data.content, 'html.parser')
        short_outcome = mini_data_soup.find('pre').text
        short_outcome = (short_outcome.split(leg))
        if len(short_outcome) > 1:
            short_outcome = short_outcome[1]
            leg1_index = int(leg_list.index(leg))
            if leg1_index != len(leg_list)-1:
                next_leg = leg_list[leg_list.index(leg)+1]
                short_outcome = (short_outcome.split(next_leg))[0]
                short_outcome = (short_outcome.split('.')[-1]).strip('.').strip()
                split_list = ["+", "HOUSE", "SENATE", "* *", "REMEMBER"]
                for word in split_list:
                    if word in short_outcome.upper():
                        short_outcome = short_outcome.split(word)[0].strip()
            # Different procedure for final legislation in list (endpt not determined by next piece of legislation)
            elif leg1_index == len(leg_list)-1:
                short_outcome = (short_outcome.split('..')[-1]).split('\n')[0].strip().strip("+").strip('.').strip()
        elif len(short_outcome) <= 1:
            short_outcome = ''
        if "SLC" in short_outcome:
            short_outcome = "Law"


        if vote_page.status_code != 404:

            soup = BeautifulSoup(vote_page.content, "html.parser")

            # Get description
            # Webpage from H0528 from 2000 formatted differently/incorrectly than all the rest. Easiest to add description for this bill manually here.
            if year == 2000 and leg == 'H0528':
                desc = 'AUDITORIUM DISTRICTS - Amends existing law to clarify the definition of auditorium districts; to clarify the petition contents; and to require the specification of a maximum rate on the hotel/motel sales tax for auditorium districts established after July 1, 2000.'
            # Obtain description for all other bills
            else:
                desc_soup = (soup.find('pre')).text
                endpt = re.search(r'[0-9][0-9]/[0-9][0-9]', desc_soup).group(0)
                desc = desc_soup.split(endpt)[0]
                splitpt = re.search('([A-Z|0-9]+.?[A-Z|0-9]* )+-', desc).group(0)
                desc = f'{splitpt}{desc.split(splitpt)[1]}'
                desc = desc.replace('\n', ' ')


            # Get long outcome
            outcome_soup = soup.find('pre').text
            split_date = re.findall('\n[0-9][0-9]/[0-9][0-9]', outcome_soup)[-1]
            outcome = outcome_soup.split(split_date)[-1]
            outcome = outcome.strip().replace('\n', ';').replace('        ', '')
            outcome = (f'{split_date} {outcome}').strip()
            outcome = outcome.replace('–', "-")
            outcome = (''.join(outcome.split('\n')))
            # Get rid of any vote counts included in outcome
            if "AYES" in outcome:
                outcome = (outcome.split('AYES'))[0]
                outcome = outcome.strip().strip(';')
            if "NAYS" in outcome:
                outcome = (outcome.split('NAYS'))[0]
                outcome = outcome.strip().strip(';')
            outcome = outcome.replace("  ", " ")


            # Get governor's action
            gov_action = ""
            if "law" in short_outcome.lower() or "veto" in short_outcome.lower():
                if "sign" in outcome.lower() and 'without' not in outcome.lower():
                    gov_action = 'Signed'
                elif "veto" in short_outcome.lower() and "line item" not in short_outcome.lower():
                    gov_action = 'Vetoed'
                elif "line item veto" in short_outcome.lower():
                    gov_action = 'Line Item Veto'
                elif 'without' in outcome.lower() and "veto" not in outcome.lower() and ("effective" in outcome.lower() or "law" in outcome.lower()):
                    gov_action = 'Passed without signature'



            # Get legislative co-sponsors
            # No cosponsor info pre-2009


            # Get floor sponsors
            floor_sponsor_page = soup.find('pre').text
            floor_sponsors = re.findall(r'Floor Sponsor.*\n.*Title', floor_sponsor_page)
            fs_list = []
            count = 1
            for sponsor in floor_sponsors:
                if count < 3:
                    sponsor = sponsor.strip('Floor Sponsor').strip('–').strip('-')
                    sponsor = sponsor.replace('Title', '')
                    split = False
                    if "," in sponsor and "&" in sponsor:
                        sponsor = re.split(',|&', sponsor)
                        split = True
                    elif "&" in sponsor and "," not in sponsor:
                        sponsor = sponsor.split('&')
                        split = True
                    elif "," in sponsor and "&" not in sponsor:
                        sponsor = sponsor.split(',')
                        split = True
                    if split == True:
                        for person in sponsor:
                            person = person.strip()
                            person = person.strip('& ')
                            if count == 1:
                                if leg.startswith('H')==True and person.startswith('Speaker') == False and person.startswith('Mr.') == False:
                                    person = f'Representative {person}'
                                elif leg.startswith('S')==True  and person.startswith('President') == False:
                                    person = f'Senator {person}'
                            elif count == 2:
                                if leg.startswith('H')==True  and person.startswith('President') == False:
                                    person = f'Senator {person}'
                                elif leg.startswith('S')==True and person.startswith('Speaker') == False and person.startswith('Mr.') == False:
                                    person = f'Representative {person}'
                            fs_list.append(person)
                    else:
                        sponsor = sponsor.strip()
                        if count == 1:
                            if leg.startswith('H')==True and sponsor.startswith('Speaker') == False and sponsor.startswith('Mr.') == False:
                                person = f'Representative {sponsor}'
                            elif leg.startswith('S')==True and sponsor.startswith('President') == False:
                                person = f'Senator {sponsor}'
                        elif count == 2:
                            if leg.startswith('H')==True and sponsor.startswith('President') == False:
                                person = f'Senator {sponsor}'
                            elif leg.startswith('S')==True and sponsor.startswith('Speaker') == False and sponsor.startswith('Mr.') == False:
                                person = f'Representative {sponsor}'
                        fs_list.append(person)
                count+=1
            if len(fs_list) == 0:
                fs_list = ''


            # Get vote dates
            vote_date_text = soup.find('pre').text.upper()
            find_chambers = vote_date_text.replace('ADOPTED', 'SPLIT_POINT').replace('FAILED', 'SPLIT_POINT').replace('PASSED', 'SPLIT_POINT')
            date_dict = {'house': '', 'senate': ''}
            try:
                find_chambers = find_chambers.split('SPLIT_POINT')[1:]
            except:
                find_chambers = None
            if find_chambers != None:
                housedate = None
                senatedate = None
                count=0
                for x in find_chambers:
                    if "VOICE VOTE" in x.upper():
                        if (count % 2 == 0 and leg.startswith("S") == True) or (count % 2 == 1 and leg.startswith("H")==True):
                            senatedate = count
                        elif (count % 2 == 0 and leg.startswith("H") == True) or (count % 2 == 1 and leg.startswith("S")==True):
                            housedate = count
                    elif "AYES" in x or "NAYS" in x.upper():
                        num_voters = re.findall(r'[0-9][0-9]? ?--? ?[0-9][0-9]? ?--? ?[0-9][0-9]?', x)
                        num_voters = list(map(lambda x: x.replace('--', '-'), num_voters))
                        num_voters = num_voters[0].split('-')
                        num_voters = list(map(lambda x: int(x), num_voters))
                        num_voters = sum(num_voters[0:])
                        # Use 60 and 40 as cutoffs to account for minor errors in the count
                        if num_voters > 60:
                            housedate = count
                        elif num_voters < 40:
                            senatedate = count
                    count+=1

                # Get house vote date
                if housedate != None:
                    house_vote_text = vote_date_text.split(find_chambers[housedate])[0]
                    house_vote_date = re.findall(r'\n[0-9][0-9]/[0-9][0-9]', house_vote_text)[-1]
                    hmonth = int(house_vote_date.split('/')[0].strip())
                    hday = int(house_vote_date.split('/')[1].split(' ')[0])
                    date_dict['house'] = date(year, hmonth, hday)

                # Get senate vote date
                if senatedate != None:
                    senate_vote_text = vote_date_text.split(find_chambers[senatedate])[0]
                    senate_vote_date = re.findall(r'\n[0-9][0-9]/[0-9][0-9]', senate_vote_text)[-1]
                    smonth = int(senate_vote_date.split('/')[0].strip())
                    sday = int(senate_vote_date.split('/')[1].split(' ')[0])
                    date_dict['senate'] = date(year, smonth, sday)


            # Determine if amended
            if year == 1998:
                amended_info = soup.find_all('h2', string = re.compile('.*Amend.*'))
                if len(amended_info) > 0:
                    amended = "Amended"
                else:
                    amended = ''
            else:
                amended_info = soup.find_all('a', string=re.compile('.*Amendment.*'))
                if len(amended_info) > 0:
                    amended = "Amended"
                else:
                    amended = ''


            # No notes
            notes = ''


        # Create variables if 404
        else:
            logging.info(f'{leg}: 404 Error')
            amended = ''
            outcome = ''
            fs_list = ''
            gov_action = ''
            desc = ''
            date_dict = {'house':'', 'senate':''}
            # 404 note
            notes = '404 Error'


        # Create dataframe row
        df_row = {"bill_num": leg, "amended": amended, "short_outcome": short_outcome, "final_action": outcome, "house_vote_date": date_dict['house'], "senate_vote_date": date_dict['senate'], "leg_cosponsors": '', "floor_sponsors": fs_list, "gov_action": gov_action, "short_desc": desc, "long_desc": '', "topics_all": '', "topics_coded": '', "t1": '', "t1_aye": '', "t2": '', "t2_aye": '', "t3": '', "t3_aye": '', "t4": '', "t4_aye": '', "t5": '', "t5_aye": '', "bill_group": '', "link": link, "notes": notes}

        leg_info_df = leg_info_df.append(df_row, ignore_index=True)
        logging.info(f'{leg}: Scraping successful')


    return leg_info_df

def main():
    # Use argparse to parse command-line arguments
    argparser = argparse.ArgumentParser(description = "Preps csv file for vote coding")

    # Add positional argument to select year
    argparser.add_argument('year', metavar='<year>', help='Selects legislative session year', choices=['1998', '1999', '2000', '2001', '2002', '2003', '2004', '2005', '2006', '2007', '2008', '2009', '2010', '2011', '2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019', '2020'])

    args = argparser.parse_args()
    year = int(args.year)

    leg_info_df = pd.DataFrame(columns = ["bill_num", "amended", "short_outcome", "final_action", "house_vote_date", "senate_vote_date", "leg_cosponsors", "floor_sponsors", "gov_action", "short_desc", "long_desc", "topics_all", "topics_coded", "t1", "t1_aye", "t2", "t2_aye", "t3", "t3_aye", "t4", "t4_aye", "t5", "t5_aye", "bill_group", "link", "notes"])

    full_leg_list = vote_scraping.get_leg(year)
    #full_leg_list = ['H0312', 'H0325', 'H0342', 'HJM012', 'HJM014', 'S1218']
    #full_leg_list = ['H0001', 'H0002', 'H0010', 'HCR004', 'H0063', 'S1001', 'S1025', 'SJR101']
    if year > 2008:
        info = get_info_post09(full_leg_list, year, leg_info_df)
    else:
        info = get_info_pre09(full_leg_list, year, leg_info_df)
    info.to_csv(f'coding_{year}_votes.csv', index=False)


if __name__ == "__main__":
    main()
