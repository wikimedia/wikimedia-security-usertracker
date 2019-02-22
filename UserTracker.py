# -*- coding: utf-8 -*-
""" User-tracking tools for various wmf-related systems
Author: sbassett@wikimedia.org
License: Apache 2.0
"""
import datetime
import json
import re
import requests
import smtplib
import socket
import syslog
import time


def send_email_notification(sender, receivers, subject, body, debug=False):
    """ Send a simple email
    :param sender: string
    :param receivers: list of strings
    :param subject: string
    :param body: string
    """
    sender_full = "{}@{}".format(sender, socket.getfqdn())
    message = """\
From: %s
To: %s
Subject: %s

%s
""" % (
        sender_full,
        ", ".join(receivers),
        subject,
        body)

    if debug:
        print(''.join(['=== debug email notification ===\nsender: ',
              sender_full, '\n\nmessage: ', message]))
    else:
        server = smtplib.SMTP('localhost')
        server.sendmail(sender_full, receivers, message)
        server.quit()


class PhabricatorTracker():
    """ Class for tracking a user's activity within Phabricator """
    def __init__(self, emails, email_debug, time_interval,
                 phab_user_name, phab_api_key):
        """ Instance Vars """
        self.emails = emails
        self.email_debug = email_debug
        self.previous_time = int(self.process_time_interval(time_interval))
        self.phab_user_name = phab_user_name
        self.phab_api_key = phab_api_key
        self.phab_base_url = 'https://phabricator.wikimedia.org/'
        self.phab_api_end_point_urls = {
            'user.search': ''.join([self.phab_base_url, 'api/user.search']),
            'phid.query': ''.join([self.phab_base_url, 'api/phid.query']),
            'maniphest.search': ''.join([self.phab_base_url,
                                        'api/maniphest.search']),
            'file.search': ''.join([self.phab_base_url, 'api/file.search']),
            'paste.query': ''.join([self.phab_base_url, 'api/paste.query']),
            'phame.post.search': ''.join([self.phab_base_url,
                                         'api/phame.post.search']),
            'phurls.search': ''.join([self.phab_base_url,
                                     'api/phurls.search']),
            'project.search': ''.join([self.phab_base_url,
                                      'api/project.search'])
        }

    def process_time_interval(self, ti):
        """ Process various time inteval formats (ns, nm, nh, nd)  """
        seconds = 0
        m = re.match(r'^(\d+)([a-zA-Z])$', ti)
        if m.group(1) and m.group(2):
            if m.group(2) == 's':
                seconds = int(m.group(1))
            elif m.group(2) == 'm':
                seconds = int(m.group(1)) * 60
            elif m.group(2) == 'h':
                seconds = int(m.group(1)) * 3600
            elif m.group(2) == 'd':
                seconds = int(m.group(1)) * 86400
            else:
                raise ValueError('Incorrect format for \
                                 time interval argument.')

            """ Return current time() - interval """
            return time.time() - seconds
        else:
            raise ValueError('Incorrect format for \
                             time interval argument.')

    def get_end_point_data(self, end_point_key, post_params):
        """ Get JSON data from gerrit API, process and load """
        api_token_dict = {'api.token': self.phab_api_key}
        if isinstance(post_params, dict):
            api_token_dict.update(post_params)
        else:
            raise ValueError('Incorrect format for post_params')

        r = requests.post(
            self.phab_api_end_point_urls[end_point_key],
            data=api_token_dict
        )

        return json.loads(r.text)

    def analyze_end_point_data(self):
        """ Check gerrit API data for relevant user activity """
        tracking_data = {}

        """ Get PHID of user """
        phid_json_data = self.get_end_point_data(
            'user.search',
            {'constraints[usernames][0]': self.phab_user_name}
        )
        user_phid = phid_json_data.get('result').get('data')[0].get('phid')

        # TODO: make all of the below paginate through
        # 100-item limit for Phab API requests
        """ Find Phab maniphest/task activity """
        maniphest_user_type_constraints = [
            'assigned',
            'authorPHIDs',
            'closerPHIDs',
            'subscribers'
        ]

        for user_type in maniphest_user_type_constraints:
            maniphest_json_data = self.get_end_point_data(
                'maniphest.search',
                {
                    ''.join(['constraints[', user_type, '][0]']): user_phid,
                    'constraints[modifiedStart]': self.previous_time,
                    'order': 'updated'
                }
            )
            for item in maniphest_json_data.get('result').get('data'):
                task = ''.join(['T', str(item.get('id'))])
                if task not in tracking_data.keys():
                    tracking_data[task] = user_type.rstrip('s').rstrip('PHID')

        # TODO: implement
        """ Find Phab file activity """
        """ Find Phab paste activity """
        """ Find Phab phame activity """
        """ Find Phab phurls activity """
        """ Find Phab projects activity """

        return tracking_data

    def send_alert(self):
        """ Analyze tracking data and email report, if necessary """
        alert_data = self.analyze_end_point_data()
        alert_msg = ''
        for k, v in alert_data.items():
            alert_msg = ''.join([alert_msg, '* <', self.phab_base_url,
                                str(k), '>  [', str(v), ']\n'])

        if len(alert_msg) > 0:
            previous_date_formatted = str(
                datetime.datetime.utcfromtimestamp(self.previous_time)
                .strftime('%Y-%m-%d %H:%M'))
            log_msg = 'Recent phabricator activity since {} for user {}: {}'\
                .format(previous_date_formatted, self.phab_user_name,
                        str(alert_data.keys())[10:-1])

            email_sender = 'PhabricatorTracker'
            email_subject = ''.join(['Phabricator User Tracking Results - ',
                                    self.phab_user_name])
            email_body = """\
The following Phabricator objects related to user {}
were found to have activity since UTC {}:

{}
""".format(
               self.phab_user_name,
               previous_date_formatted,
               alert_msg)

            send_email_notification(
                email_sender,
                [self.emails],
                email_subject,
                email_body,
                self.email_debug)

            if self.email_debug:
                print(log_msg)
            else:
                syslog.syslog(log_msg)
        else:
            print('No recent phabricator activity found for user {}.'.format(
                  self.phab_user_name))


class GerritTracker():
    """ Class for tracking a user's activitiy within Gerrit """
    def __init__(self, emails, email_debug, time_interval,
                 gerrit_user_name, gerrit_user_id):
        """ Instance Vars """
        self.emails = emails
        self.email_debug = email_debug
        self.previous_time = self.process_time_interval(time_interval)
        self.gerrit_user_name = gerrit_user_name
        self.gerrit_user_id = int(gerrit_user_id)
        self.gerrit_base_url = 'https://gerrit.wikimedia.org/r/'
        self.gerrit_end_point_url = ''.join([self.gerrit_base_url,
                                             'changes/?q=is:open+owner:',
                                             self.gerrit_user_name,
                                             '&q=is:open+reviewer:',
                                             self.gerrit_user_name,
                                             '+-owner:',
                                             self.gerrit_user_name,
                                             '&q=is:closed+owner:',
                                             self.gerrit_user_name,
                                             '&o=LABELS'])

    def process_time_interval(self, ti):
        """ Process various time inteval formats (ns, nm, nh, nd)  """
        seconds = 0
        m = re.match(r'^(\d+)([a-zA-Z])$', ti)
        if m.group(1) and m.group(2):
            if m.group(2) == 's':
                seconds = int(m.group(1))
            elif m.group(2) == 'm':
                seconds = int(m.group(1)) * 60
            elif m.group(2) == 'h':
                seconds = int(m.group(1)) * 3600
            elif m.group(2) == 'd':
                seconds = int(m.group(1)) * 86400
            else:
                raise ValueError('Incorrect format for \
                                 time interval argument.')

            """ Return current time() - interval """
            return time.time() - seconds
        else:
            raise ValueError('Incorrect format for \
                             time interval argument.')

    def get_end_point_data_raw(self):
        """" Get raw JSON data from gerrit API """
        r = requests.get(self.gerrit_end_point_url)
        return r.text

    def get_end_point_data(self):
        """ Get JSON data from gerrit API, process and load """
        r = requests.get(self.gerrit_end_point_url)
        return json.loads(r.text[r.text.find('\n')+1:r.text.rfind('\n')])

    def analyze_end_point_data(self):
        """ Check gerrit API data for relevant user activity """
        tracking_data = {}

        for obj1 in self.get_end_point_data():
            #  todo: check against self.time_interval, remove dups,
            # add user id cats from json
            if isinstance(obj1, list):
                for obj2 in obj1:
                    gerrit_last_updated = int(datetime.datetime.strptime(
                        obj2['updated'].split('.', 1)[0],
                        "%Y-%m-%d %H:%M:%S").timestamp())
                    if(self.previous_time <= gerrit_last_updated):
                        user_info = []
                        gerrit_ps_id = obj2['_number']

                        if('owner' in obj2.keys() and
                           obj2['owner']['_account_id'] == self.gerrit_user_id
                           ):
                            user_info.append('Owner')
                        if('submitter' in obj2.keys() and
                                obj2['submitter']['_account_id'] ==
                                self.gerrit_user_id):
                            user_info.append('Submitter')
                        if('labels' in obj2.keys()):
                            for label in obj2['labels']:
                                if isinstance(obj2['labels'][label], dict):
                                    for sub_label in obj2['labels'][label]:
                                        if(isinstance(obj2['labels'][label]
                                           [sub_label], dict) and
                                           '_account_id' in
                                           obj2['labels'][label]
                                           [sub_label].keys() and
                                           obj2['labels'][label]
                                           [sub_label]['_account_id']
                                           == self.gerrit_user_id):
                                            user_info.append(label)
                        if(len(user_info) > 0):
                            if gerrit_ps_id in tracking_data.keys():
                                tracking_data[gerrit_ps_id].append(user_info)
                            else:
                                tracking_data[gerrit_ps_id] = user_info

        return tracking_data

    def send_alert(self):
        """ Analyze tracking data and email report, if necessary """
        alert_data = self.analyze_end_point_data()
        alert_msg = ''
        for k, v in alert_data.items():
            alert_msg = ''.join([alert_msg, '* <', self.gerrit_base_url,
                                str(k), '>  ', str(v), '\n'])

        if len(alert_msg) > 0:
            previous_date_formatted = str(
                datetime.datetime.utcfromtimestamp(self.previous_time)
                .strftime('%Y-%m-%d %H:%M'))
            log_msg = 'Recent gerrit activity since {} for user {}: {}'\
                .format(previous_date_formatted, self.gerrit_user_name,
                        str(alert_data.keys())[10:-1])

            email_sender = 'GerritTracker'
            email_subject = ''.join(['Gerrit User Tracking Results - ',
                                    self.gerrit_user_name])
            email_body = """\
The following gerrit patch sets related to user {}
were found to have activity since UTC {}:

{}
""".format(
               self.gerrit_user_name,
               previous_date_formatted,
               alert_msg)

            send_email_notification(
                email_sender,
                [self.emails],
                email_subject,
                email_body,
                self.email_debug)

            if self.email_debug:
                print(log_msg)
            else:
                syslog.syslog(log_msg)
        else:
            print('No recent gerrit activity found for user {}.'.format(
                  self.gerrit_user_name))
