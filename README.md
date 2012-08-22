# Overview

Welcome to push tool, I love you!

# Configuration

The tool will look for ini files in `/etc/push.ini` and `~/.push.ini`. Options
in the latter override those in the former. Most of them should probably be
left the same by all users, but some (particularly the SSH configuration) could
be useful to configure individually. See `etc/push.ini.example` for a complete
example configuration.

Configuration is divided into a few sections:

## defaults

Some basic defaults for CLI options that can be overridden in user-configs.

* `sleeptime` -- duration to wait between hosts.
* `shuffle` -- whether or not to shuffle the hostlist before deploy.

## dns

A DNS zone transfer is used to grab a list of all hosts that can be pushed to.

* `domain` -- the domain to do a zone transfer from.

## aliases

Aliases are mnemonics for a commonly used set of hosts to push to. You can
directly specify hostnames as part of a group, glob them, or include other
aliases within an alias.

```ini
[aliases]
apps = app-* job-*
dbs = pg-*
all = @apps @dbs
```

## ssh

* `user` -- the username to use when connecting to servers.
* `key_filename` -- which key file to use for ssh connections.
* `strict_host_key_checking` -- should ssh be strict about host keys? defaults to on.
* `timeout` -- how long to wait before timing out, defaults to 30 seconds.

## paths

* `log_root` -- the directory to store push logs in.
* `wordlist` -- where to find a list of words to choose push names from.

## deploy

* `build_host` -- which host to run build commands on.
* `deploy_binary` -- the root command to execute for deploy-commands.
* `build_binary` -- the root command to execute for build-commands.

## syslog

Some basic notifications of deploys starting/ending are sent to syslog for
tracking in external services.

* `ident` -- the syslog ident to use for log messages. defaults to "deploy".
* `facility` -- the syslog facility to use.
* `priority` -- the syslog priority to use.

## harold

Notification and status updates for deploys are sent to an IRC channel via
our IRC bot [Harold](http://github.com/spladug/harold).

Configuration is done through [Wessex](http://github.com/spladug/wessex)'s
configuration file.

# Future

Plans for the future include:

* move from SSH to MCollective.
  * and better parallelization as a result
* build a complete package on the build server to avoid Cython/i18n recompilation.
