import json

m_list = ['gh', 'sth']
json_list = json.dumps(m_list)
#print(json_list)

with open("sample.json", "w") as outfile:
    json.dump(m_list, outfile)

with open('./sample.json', 'r') as openfile:
    json_obj = json.load(openfile)
print(json_obj)

for i in json_obj[0:1]:
    print(i)


'''f = open(".\male_member_links.txt", 'r')
print(f.read())
all_members = []
for items in f:
    all_members.append(items)
print(all_members)
f.close()
'''
