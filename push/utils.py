import hashlib
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
            word = unicode(wordlist.readline().rstrip("\n"), 'utf-8')

    return word


def seeded_shuffle(seedword, list):
    list.sort(key=lambda h: hashlib.md5(seedword + h).hexdigest())
