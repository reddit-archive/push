import os
import sys
import random
import getpass
import datetime


__all__ = ["Log", "register"]


RED = 31
GREEN = 32
YELLOW = 33
BLUE = 34
MAGENTA = 35
CYAN = 36
WHITE = 37
WORDLIST = "/usr/share/dict/words"


def colorize(text, color, bold):
    if color:
        boldizer = "1;" if bold else ""
        start_color = "\033[%s%dm" % (boldizer, color)
        end_color = "\033[0m"
        return "".join((start_color, text, end_color))
    else:
        return text


def get_random_word():
    file_size = os.path.getsize(WORDLIST)
    word = ""

    with open(WORDLIST, "r") as wordlist:
        while not word.isalpha() or not word.islower() or len(word) < 5:
            position = random.randint(1, file_size)
            wordlist.seek(position)
            wordlist.readline()
            word = wordlist.readline().rstrip("\n")

    return word


class Log(object):
    def __init__(self, config, args):
        self.args = args

        # generate a unique id for the push
        self.push_id = get_random_word()

        # build the path for the logfile
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H:%M:%S")
        log_name = "-".join((timestamp, self.push_id)) + ".log"
        self.log_path = os.path.join(config.paths.log_root, log_name)

        # open the logfile
        self.logfile = open(self.log_path, "w")

    def write(self, text, color=None, bold=False, newline=False, stdout=True):
        suffix = "\n" if newline else ""
        self.logfile.write(text + suffix)
        if stdout:
            sys.stdout.write(colorize(text, color, bold) + suffix)
        self.flush()

    def flush(self):
        self.logfile.flush()
        sys.stdout.flush()

    def debug(self, message, *args):
        self.write(message % args,
                   newline=True,
                   color=GREEN,
                   stdout=not self.args.quiet)

    def info(self, message, *args):
        self.write(message % args,
                   newline=True,
                   stdout=not self.args.quiet)

    def notice(self, message, *args):
        self.write(message % args,
                   newline=True,
                   color=BLUE,
                   bold=True,
                   stdout=not self.args.quiet)

    def warning(self, message, *args):
        self.write(message % args,
                   newline=True,
                   color=YELLOW,
                   bold=True)

    def critical(self, message, *args):
        self.write(message % args,
                   newline=True,
                   color=RED,
                   bold=True)

    def close(self):
        self.logfile.close()


def register(config, args, deployer, log):
    @deployer.push_began
    def on_push_began(deployer):
        user = getpass.getuser()
        time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        args = " ".join(sys.argv[1:])
        log.write("Push started by %s at %s "
                  "UTC with args: %s" % (user, time, args),
                  newline=True, stdout=False)
