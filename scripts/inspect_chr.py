import os

path = '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default/chart01.chr'
with open(path, 'rb') as f:
    text = f.read().decode('utf-16le', errors='ignore')

# Print chart without the <object>...</object> spam
lines = text.splitlines()
clean_lines = []
skip = False
for line in lines:
    if '<object>' in line:
        skip = True
    elif '</object>' in line:
        skip = False
        continue
    if not skip:
        clean_lines.append(line)

print('\n'.join(clean_lines))
