import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import requests
import time
import json

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
driver = webdriver.Chrome('./chromedriver')

main_link = 'https://lrl.texas.gov/legeLeaders/members/lrlhome.cfm'
driver.get(main_link)
gender_select = Select(driver.find_element_by_xpath("//select[@name='gender']")).select_by_value('m')
#male_page_select = gender_select.select_by_value('m')
search_page = driver.find_element_by_xpath('//*[@id="search"]/table/tbody/tr[7]/td[2]/input[1]')
search_page.click()
time.sleep(3)
pageSource = driver.page_source

#Crawl to get links
soup = BeautifulSoup(pageSource, 'html.parser')
table = soup.find_all('tbody')
all_links = []
for i in soup.find('tbody').find_all('tr'):
    all_links.append(i.find('a')['href'])

#with open(".\male_member_links.txt", "w") as f:
#    for items in all_links:
#        f.write("%s," %items)
#f.close()

with open("male_member.json", "w") as outfile:
    json.dump(all_links, outfile)

#f = open(".\male_member_links.txt", "w")
#f.writelines(all_links)
#f.close()
