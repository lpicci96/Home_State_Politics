import pandas as pd
import numpy as np
import time
from bs4 import BeautifulSoup
from urllib.request import urlopen
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from selenium.webdriver.chrome.options import Options
import os

'''
Luca Picci
updated: 8/11/2021

This script pulls data on Florida state senators from https://www.flsenate.gov
'''

#--- INITIALIZATION ---------------------------------------------------------------------------
base_url = r'https://www.flsenate.gov/Senators/' 
driver_path = r"C:\Users\lpicc\OneDrive\Documents\drivers\chromedriver_win32 - 92\chromedriver.exe" #chrome driver
export_path = r"C:\Users\lpicc\OneDrive\Documents\HSP\Florida\senators.csv" # export path for csv

session_to_download = '2020-2022' #   <----- set session to download
download_all = True              #   <----- set to False to download only one session

#--- MAIN SCRIPT -------------------------------------------------------------------------------------------

start_time = time.time()

data = pd.DataFrame(columns=['term', 'name', 'district', 'party', 'counties', 'image_link', 'senator_link'])
if download_all == True:
    driver = webdriver.Chrome(driver_path)
    driver.get(base_url)
    drop_down = driver.find_element_by_id('UserSelectedTerm')
    drop_down_options = Select(drop_down)
    session_list = []
    for i in drop_down_options.options:
        session_list.append(i.get_attribute('value'))
    driver.quit()
    time.sleep(1)

else:
    session_list = [session_to_download]



for i in range(len(session_list)):
    term = session_list[i]
    
    print(' ', '#'*(i+1), '-'*(len(session_list) - i), '|', round((i/len(session_list))*100, 2), '%', end = '\r')
    session_url = base_url+session_list[i]
    
    webcontent = urlopen(session_url)
    html_page = webcontent.read()
    webcontent.close()
    time.sleep(1)
    soup = BeautifulSoup(html_page, 'lxml')
    
    table = soup.find_all('table')[0]
    row_len = len(table.find_all('tr'))
    
    for j in range(1,row_len-1):
        row = table.find_all('tr')[j]
        #name
        name = row.find_all('th')[0].text.strip()
        #image link
        image = 'https://www.flsenate.gov'+row.a.img['src']
        #district
        district = eval(row.find_all('td')[0].text)
        #party
        party = row.find_all('td')[1].text
        #senator link
        senator_link = 'https://www.flsenate.gov' + row.a.get('href')
        #counties
        counties = row.find_all('td')[2].text

        session_dict = {'term': term, 'name': name, 'district':district, 'party':party, 
                        'counties':counties, 'image_link': image, 'senator_link':senator_link
                       }
        data = data.append(session_dict, ignore_index = True)
    
new = data.name.str.split('\n', expand=True)
data['name'] = new[0]
data['position'] = new[1]
new = data.position.str.split('Resigned', expand=True)
if len(new.columns)>1:
    data['resigned'] = new[1]
    new.drop(1, 1, inplace=True)
else:
    data['resigned'] = np.nan

new = new[0].str.split('Died in Office', expand=True)
if len(new.columns)>1:
    data['died_in_office'] = new[1]
    new.drop(1, 1, inplace=True)
else:
    data['died_in_office'] = np.nan

new = new[0].str.split('Elected', expand=True)
if len(new.columns)>1:
    data['elected'] = new[1]
else:
    data['elected'] = np.nan
    
data['position'] = new[0]
data.loc[data.position == '', 'position'] = np.nan
data.fillna(np.nan, inplace=True)
data.to_csv(export_path, index=False)

#------------------------------------------------------------------------------------------------------
print()
end_time = round(time.time()- start_time, 2)
print('------')
print(f'complete in {end_time} s')
print('------')
#------------------------------------------------------------------------------------------------------