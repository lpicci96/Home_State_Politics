import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import requests

male_members_page = 'https://lrl.texas.gov/legeLeaders/members/membersearch.cfm'
call_request = requests.get(male_members_page)
soup = BeautifulSoup(call_request.content, 'html.parser')
print(soup.prettify())
