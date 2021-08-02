all_links = ['lied', 'life']
with open('.\male_member_links.txt', 'w') as f:
    for items in all_links:
        f.write('%s,' %items)
f.close()



'''open_txt = open("\male_member_links.txt", "w")
for items in all_links:
    open_txt.writelines(items)
open_txt.close()'''