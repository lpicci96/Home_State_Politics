import pandas as pd
import numpy as np
import time
from bs4 import BeautifulSoup
import urllib
from urllib.request import urlopen
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from selenium.webdriver.chrome.options import Options
import os
import requests

'''
Luca Picci 
updated: 9/10/2021

This script pulls data on Florida state representatives from 
https://www.myfloridahouse.gov
'''

#--- INITIALIZATION ----------------------------------------------------------------------------------

base_url = "https://www.myfloridahouse.gov"
rep_url = base_url+"/representatives"

driver_path = r"C:\Users\lpicc\OneDrive\Documents\drivers\chromedriver_win32 - 92\chromedriver.exe" #chrome driver path
export_path = r"C:\Users\lpicc\OneDrive\Documents\HSP\Florida\representatives.csv" #export path for csv

#--- MAIN SCRIPT---------------------------------------------------------------------------------------
start_time = time.time()

driver = webdriver.Chrome(driver_path)
driver.get(rep_url)
drop_down = driver.find_element_by_id('ddlTerm')
drop_down_options = Select(drop_down)
session_list = []
for i in drop_down_options.options:
    session_list.append(i.get_attribute('value'))
driver.quit()
session_list = ['?legislativetermid=' + string for string in session_list]

data = pd.DataFrame(columns=['term', 'name', 'district', 'party', 'counties', 
                             'image_link', 'senator_link', 'speaker'])

for i in range(len(session_list)):
    
    print(' ', '#'*(i+1), '-'*(len(session_list) - i), '|', round((i/len(session_list))*100, 2), '%', end = '\r')
    
    session_url = rep_url+session_list[i]
    page = requests.get(session_url)
    soup = BeautifulSoup(page.text, 'lxml')

    speaker_session = soup.find('title').text.split('|')[0].split('(')
    term = speaker_session[0].strip('\r\n\tRepresentatives for')
    speaker = speaker_session[1].strip(') ')

    rep_all = soup.find_all('div', {'class':'team-box'})
    for j in range(len(rep_all)):
        rep = rep_all[j]
        rep = rep.find_all('a')[0]
        name = rep.find('h5').text.strip()

        image = rep.find('img').get('data-src')
        image_link = base_url+image

        party_rep = rep.find_all('p')[0].text
        party_rep = party_rep.split('—')
        party = party_rep[0].strip()
        district = party_rep[1].strip('District: ')
        district = district.strip()

        counties = rep.find('p', {'class':'rep-counties'}).text

        senator_link = base_url + rep['href']

        session_dict = {'term': term, 'name': name, 'district':district, 'party':party, 
                        'counties':counties, 'image_link': image_link, 'senator_link':senator_link,
                        'speaker':speaker
                       }
        data = data.append(session_dict, ignore_index = True)

        
data.to_csv(export_path, index=False)     

#----------------------------------------------------------------------------------------------------
print()
end_time = round(time.time()- start_time, 2)
print('------')
print(f'complete in {end_time} s')
print('------')
#----------------------------------------------------------------------------------------------------

