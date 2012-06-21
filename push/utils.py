import os
import random


def get_random_word(config):
    file_size = os.path.getsize(config.paths.wordlist)
    word = ""

    with open(config.paths.wordlist, "r") as wordlist:
        while not word.isalpha() or not word.islower() or len(word) < 5:
            position = random.randint(1, file_size)
            wordlist.seek(position)
            wordlist.readline()
            word = wordlist.readline().rstrip("\n")

    return word
