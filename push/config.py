from __future__ import absolute_import

import os
import collections
import ConfigParser


NoDefault = object()
SECTIONS = collections.OrderedDict()


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


def _make_extractor(cls, prefix="", required=True):
    section_name = cls.__name__[:-len("config")].lower()
    if prefix:
        section_name = prefix + ":" + section_name

    def config_extractor(parser):
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

    config_extractor.required = required
    config_extractor.prefix = prefix
    SECTIONS[section_name] = config_extractor


def config_section(*args, **kwargs):
    if len(args) == 1 and not kwargs:
        # bare decorator "@config_section" style
        return _make_extractor(args[0])

    def config_decorator(cls):
        return _make_extractor(cls, **kwargs)
    return config_decorator


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
class HostsConfig(object):
    def valid_host_source(value):
        try:
            section = SECTIONS["hosts:" + value]
        except KeyError:
            raise ValueError("invalid host source: %r" % value)
        section.required = True
        return value
    source = Option(valid_host_source)


@config_section(prefix="hosts", required=False)
class DnsConfig(object):
    domain = Option(str)


@config_section(prefix="hosts", required=False)
class MockConfig(object):
    host_count = Option(int)


@config_section(prefix="hosts", required=False)
class ZooKeeperConfig(object):
    connection_string = Option(str)
    username = Option(str)
    password = Option(str)


@config_section
class DefaultsConfig(object):
    sleeptime = Option(int, default=0)
    shuffle = Option(boolean, default=False)


def alias_parser(parser):
    aliases = {}
    if parser.has_section("aliases"):
        for key, value in parser.items("aliases"):
            aliases[key] = [glob.strip() for glob in value.split(' ')]
    return aliases
SECTIONS["aliases"] = alias_parser


def default_ref_parser(parser):
    default_refs = {}
    if parser.has_section("default_refs"):
        default_refs.update(parser.items("default_refs"))
    return default_refs
SECTIONS["default_refs"] = default_ref_parser


def parse_config():
    """Loads the configuration files and parses them according to the
    section parsers in SECTIONS."""
    parser = ConfigParser.RawConfigParser()
    parser.read(["/opt/push/etc/push.ini", os.path.expanduser("~/.push.ini")])

    config = attrdict()
    for name, section_parser in SECTIONS.iteritems():
        is_required = getattr(section_parser, "required", True)
        if is_required or parser.has_section(name):
            prefix = getattr(section_parser, "prefix", None)
            parsed = section_parser(parser)
            if not prefix:
                config[name] = parsed
            else:
                unprefixed = name[len(prefix) + 1:]
                config.setdefault(prefix, attrdict())[unprefixed] = parsed

    return config
