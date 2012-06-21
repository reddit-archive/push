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


def _seed_from_word(word):
    return sum(ord(c) for c in word)


def seeded_shuffle(seedword, list):
    state = random.getstate()

    seed = _seed_from_word(seedword)
    random.seed(seed)
    random.shuffle(list)

    random.setstate(state)
