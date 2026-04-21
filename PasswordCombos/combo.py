# Need two integers followed by two letters.
# i.e. 00aa, 00ab, 00ac, ..., 99zy, 99zz
import string

with open("output.txt", "w") as file:
    for i in range(100):
        padded_string = str(i)
        padded_numbers = padded_string.zfill(2)
        for letter1 in string.ascii_lowercase:
            for letter2 in string.ascii_lowercase:
                file.write(padded_numbers + letter1 + letter2 + "\n")
