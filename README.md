# UserTracker

Python tooling to monitor certain activities within Gerrit and Phabricator.  See ```./bin/GerritTracker -h``` or ```./bin/PhabricatorTracker -h``` for command-line arguments.

## Prerequisites

```
Python 3 stdlib
argparse
datetime
json
os
re
requests
smtplib
socket
sys
syslog
time
```

## Installing

1. ```git clone "https://gerrit.wikimedia.org/r/wikimedia/security/usertracker"```

## Options

Command-line options to pass.  Most are required.

* ```-h, --help``` - show this help message and exit
* ```-e EMAILS, --emails EMAILS``` - email or comma-separated list of emails to notify
* ```-d EMAILDEBUG, --emaildebug EMAILDEBUG``` - email debug flag (True or False)
* ```-t TIMEINTERVAL, --timeinterval TIMEINTERVAL``` - time interval (e.g. 1d, 2m, etc - see process_time_interval)
* ```-u GUSERNAME, --gusername GUSERNAME``` - gerrit username to track
* ```-i GUSERID, --guserid GUSERID``` - gerrit user id to track (corresponds to --gusername)

## Usage

1. Simply run the appropriate tracker in ```/bin``` with the above options specified.  e.g.

```./bin/GerritTracker -e test@example.com -t 1d -u nobody -i 1111```

**OR**

2. Set up as a cron (e.g. every 2 minutes):

```*/2 * * * * ./bin/GerritTracker -e test@example.com -t 1d -u nobody -i 1111```

## Known Issues

* See TODOs in ```UserTracker.py```

## Authors

* **Scott Bassett** [sbassett@wikimedia.org]

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
