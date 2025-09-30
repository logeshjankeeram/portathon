import re

line = r'\s:KlaipedaVTS,c:1758574798*59\!AIVDM,1,1,,B,24SR`F0000QPgE0OoVBUUrUj0@R9,0*75'
print('Line:', line)

# Test timestamp extraction
timestamp_match = re.search(r'c:(\d+)', line)
print('Timestamp match:', timestamp_match)
if timestamp_match:
    print('Timestamp:', timestamp_match.group(1))

# Test AIS data extraction
ais_match = re.search(r'!AIVDM,\d+,\d+,,.,([^,]+)', line)
print('AIS match:', ais_match)
if ais_match:
    print('AIS data:', ais_match.group(1))

# Try alternative pattern
ais_match2 = re.search(r'!AIVDM,.*?,([^,]+)', line)
print('AIS match2:', ais_match2)
if ais_match2:
    print('AIS data2:', ais_match2.group(1))
