from ais_parser import AISParser
from datetime import datetime
import re

parser = AISParser()

# Read first 100 lines and check message types
with open('../kazkas/Log_2025-09-23.log', 'r') as f:
    message_types = {}
    for i, line in enumerate(f):
        if i >= 100:
            break
            
        parsed = parser.parse_nmea_line(line.strip())
        if parsed:
            msg_type = parsed.get('message_type')
            if msg_type:
                message_types[msg_type] = message_types.get(msg_type, 0) + 1
        else:
            # Try to extract message type from binary
            ais_match = re.search(r'!AIVDM,\d+,\d+,,.,([^,]+)', line.strip())
            if ais_match:
                ais_data = ais_match.group(1)
                binary = parser._ais_to_binary(ais_data)
                if binary and len(binary) >= 6:
                    msg_type = int(binary[:6], 2)
                    message_types[msg_type] = message_types.get(msg_type, 0) + 1

print("Message types found:")
for msg_type, count in sorted(message_types.items()):
    print(f"Type {msg_type}: {count} messages")
