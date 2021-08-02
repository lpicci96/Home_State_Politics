import pandas as pd
import numpy as np
from helium import *
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from urllib.parse import urljoin
import requests
import time
import json
from furl import furl
from selenium.webdriver import Firefox
from selenium.webdriver.support.ui import Select



driver = Firefox(executable_path='.\geckodriver.exe')
main_link = 'https://lrl.texas.gov/legeLeaders/members/membersearch.cfm'
f = furl(main_link)
a = f'{str(f.origin)}/{f.path.segments[0]}/{f.path.segments[1]}/'
helium.set_driver(driver)
go_to(main_link)

gender_select = driver.find_element_by_xpath("//select[@name='gender']/option[3]").click()
#driver.find_element_by_xpath("//*[@id='search']/table/tbody/tr[1]/td[2]/select/option[3]").click()
driver.find_element_by_xpath("//input[@type='SUBMIT']").click()
print(find_all(S("//td[contains(results")))


#print(gender_select.options)
#/option[value='m']")
#.click()
#gender_select.select_
#.find_element_by_text('M ').click()
#gender_select.find_element_by_visible_text('M ').click()
#helium.select(ComboBox('gender'),'M ')

#driver.get(main_link)



#print(f)

#furl(main_link).remove(['membersearch.cfm']).url


'''main_link_parse = urlparse(main_link)
#print(main_link_parse.scheme)
main_link1 = main_link_parse._replace(path = '/legeLeaders/members/')
#print(main_link1)

main_link2 = urljoin(main_link_parse.scheme, main_link_parse.netloc, main_link_parse.path)
#print(main_link2)

new_main_link = main_link_parse.scheme + '://' + main_link_parse.netloc + '/legeLeaders/members/'

#print(main_link_parse.scheme, main_link_parse.netloc, main_link_parse.path)
#main_path_string = str(main_link_parse.path)
#print(main_path_string[0:-16])


with open('./male_member.json', 'r') as openfile:
    json_obj = json.load(openfile)

print(new_main_link+json_obj[0])'''

#for link in json_obj:
 #   print(link)
