from __future__ import absolute_import

import os
import ConfigParser


NoDefault = object()
SECTIONS = {}


class attrdict(dict):
    "A dict whose keys can be accessed as attributes."
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dict__ = self


class ConfigurationError(Exception):
    "Exception to raise when there's a problem with the configuration file."
    def __init__(self, section, name, message):
        self.section = section
        self.name = name
        self.message = message

    def __str__(self):
        return 'section "%s": option "%s": %s' % (self.section,
                                                  self.name,
                                                  self.message)


def boolean(input):
    """Converter that takes a string and tries to divine if it means
    true or false"""
    if input.lower() in ("true", "on"):
        return True
    elif input.lower() in ("false", "off"):
        return False
    else:
        raise ValueError('"%s" not boolean' % input)


class Option(object):
    "Declarative explanation of a configuration option."
    def __init__(self, convert, default=NoDefault, validator=None):
        self.convert = convert
        self.default = default
        self.validator = validator


def config_section(cls):
    """Decorator to apply to a declarative class describing a config section.
    Options within the section are parsed and stored in a dict."""
    section_name = cls.__name__[:-len("config")].lower()

    def config_extractor(section_name, parser):
        section = attrdict()
        for name, option_def in vars(cls).iteritems():
            if not isinstance(option_def, Option):
                continue

            try:
                value = parser.get(section_name, name)
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                if option_def.default is NoDefault:
                    raise ConfigurationError(section_name, name,
                                             "required but not present")
                value = option_def.default
            else:
                try:
                    value = option_def.convert(value)
                except Exception, e:
                    raise ConfigurationError(section_name, name, e)

            section[name] = value
        return section

    SECTIONS[section_name] = config_extractor
    return config_extractor


@config_section
class SshConfig(object):
    user = Option(str)
    key_filename = Option(str, default=None)
    strict_host_key_checking = Option(boolean, default=True)
    timeout = Option(int, default=30)


@config_section
class DeployConfig(object):
    build_host = Option(str)
    deploy_binary = Option(str)
    build_binary = Option(str)


@config_section
class PathsConfig(object):
    log_root = Option(str)
    wordlist = Option(str, default="/usr/share/dict/words")


@config_section
class SyslogConfig(object):
    def syslog_enum(value):
        import syslog
        value = "LOG_" + value
        return getattr(syslog, value)

    ident = Option(str, default="deploy")
    facility = Option(syslog_enum)
    priority = Option(syslog_enum)


@config_section
class DnsConfig(object):
    domain = Option(str)

@config_section
class DefaultsConfig(object):
    sleeptime = Option(int, default=5)
    shuffle = Option(boolean, default=False)


def alias_parser(section_name, parser):
    aliases = {}
    if parser.has_section("aliases"):
        for key, value in parser.items("aliases"):
            aliases[key] = [glob.strip() for glob in value.split(' ')]
    return aliases
SECTIONS["aliases"] = alias_parser


def parse_config():
    """Loads the configuration files and parses them according to the
    section parsers in SECTIONS."""
    parser = ConfigParser.RawConfigParser()
    parser.read(["/opt/push/etc/push.ini", os.path.expanduser("~/.push.ini")])

    config = attrdict()
    for name, section_parser in SECTIONS.iteritems():
        config[name] = section_parser(name, parser)
    return config
