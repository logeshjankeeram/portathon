from ais_parser import AISParser
from datetime import datetime

parser = AISParser()

# Test data
ais_data = "24SR`F0000QPgE0OoVBUUrUj0@R9"
timestamp = datetime.fromtimestamp(1758574798)

print(f"AIS data: {ais_data}")
print(f"Timestamp: {timestamp}")

# Test binary conversion
binary = parser._ais_to_binary(ais_data)
print(f"Binary: {binary}")
print(f"Binary length: {len(binary)}")

if binary:
    # Test message type extraction
    message_type = int(binary[:6], 2)
    print(f"Message type: {message_type}")
    
    # Test parsing
    result = parser.parse_ais_message(ais_data, timestamp)
    print(f"Parse result: {result}")
else:
    print("Binary conversion failed")
