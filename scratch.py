import re
with open('app/module3/report_data.py', 'r') as f:
    text = f.read()

# Replace claimant parsing for Homeowner
text = text.replace('claimant = {\n                        "name": homeowner_row[0] or claimant["name"],', 'claimant = {\n                        "name": full_name or homeowner_row[0] or claimant["name"],')

with open('app/module3/report_data.py', 'w') as f:
    f.write(text)
