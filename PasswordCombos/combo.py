# Need two integers followed by two letters.
# i.e. 00aa, 00ab, 00ac, ..., 99zy, 99zz
import string

for i in range(100):
    padded_string = str(i)
    padded_numbers = padded_string.zfill(2)
    for letter1 in string.ascii_lowercase:
        for letter2 in string.ascii_lowercase:
            print(padded_numbers + letter1 + letter2)
