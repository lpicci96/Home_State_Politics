import codecs
from bs4 import BeautifulSoup

member_page = codecs.open("page.html", 'r')
soup = BeautifulSoup(member_page.content, 'html.parser')
print('soup parsed')

