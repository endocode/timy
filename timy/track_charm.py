#!/usr/bin/env python

"""Charm2RedmineTT

Usage:
  timy list projects
  timy list activities
  timy list users
  timy list timetracks [--verbose | -v] [--days=<days> | --startdate=<start_date>] [--enddate=<end_date>] [--sumday] [--user=<userid>]
  timy trackxml <EXPORTFILE> [--submit | -S] [--starteventid=<event_id>] [--startdate=<start_date>] [--enddate=<end_date>] [--no-ask | -n]
  timy trackdb [DBFILE] [--submit | -S] [--starteventid=<event_id>] [--startdate=<start_date>] [--enddate=<end_date>] [--no-ask | -n]
  timy (-h | --help)
  timy --version

Options:
  -h --help                     Show this screen.
  --version                     Show version.
  -v --verbose                  Print more information.
  --starteventid=<event_id>     Skip events before event_id.
  --startdate=<start_date>      Skip events before start_date (YYYY-MM-DD)
  --enddate=<end_date>          Skip events after end_date (YYYY-MM-DD)
  -S --submit                   Actually create time tracks in Redmine.
  -n --no-ask                   Don't ask before submitting a time track.
  --days=<days>                 Print time tracks for the last <days> otherwise print current month
  --user=<username>             Act as <username>

"""

from redminelib import Redmine
from redminelib.exceptions import ResourceSetIndexError, ValidationError
from datetime import date, timedelta, datetime
from os.path import expanduser, join
import numpy
import json
import docopt
import sys

datetime_fmt = "%Y-%m-%dT%H:%M:%SZ"
cmdlinedate_fmt = "%Y-%m-%d"
almost_a_day = 86399
sqlite_date_fmt = "%Y-%m-%dT%H:%M:%S"

class CharmTimeTracking(object):

    def __init__(self, arguments):
        self.verbose = arguments["--verbose"]
        self.sumday = arguments["--sumday"]
        self.start_from_date = None
        self.end_at_date = None
        self.start_event_id = 1
        self.db_path = None
        self.submit = False
        self.ask = True
        self.user = int(arguments["--user"]) if arguments["--user"] else "current"

        if arguments['list'] and arguments['projects']:
            self.processing_func = self.print_all_projects

        if arguments['list'] and arguments['activities']:
            self.processing_func = self.print_activity_ids

        if arguments['list'] and arguments['users']:
            self.processing_func = self.print_all_users

        if arguments['list'] and arguments['timetracks']:
            if arguments["--days"]:
                self.start_from_date = date.today() - timedelta(days=int(arguments["--days"]))
            else:
                if arguments["--startdate"]:
                    self.start_from_date = datetime.strptime(arguments["--startdate"], cmdlinedate_fmt).date()
                else:
                    self.start_from_date = date.today().replace(day=1)
            if arguments["--enddate"]:
                self.end_at_date = datetime.strptime(arguments["--enddate"], cmdlinedate_fmt).date()

            self.processing_func = self.print_time_tracks_from

        if arguments['trackxml'] and arguments['<EXPORTFILE>']:
            if arguments["--startdate"]:
                self.start_from_date = datetime.strptime(arguments["--startdate"], cmdlinedate_fmt)
            if arguments["--enddate"]:
                self.end_at_date = datetime.strptime(arguments["--enddate"], cmdlinedate_fmt) + timedelta(seconds=almost_a_day)
            if arguments["--starteventid"]:
                self.start_event_id = int(arguments["--starteventid"])
            if arguments["--submit"]:
                self.submit = True
            if arguments["--no-ask"]:
                self.ask = False

            self.xml_export_path = arguments["<EXPORTFILE>"]

            self.processing_func = self.parse_xml

        if arguments['trackdb']:
            if arguments["--startdate"]:
                self.start_from_date = datetime.strptime(arguments["--startdate"], cmdlinedate_fmt)
            if arguments["--enddate"]:
                self.end_at_date = datetime.strptime(arguments["--enddate"], cmdlinedate_fmt) + timedelta(days=1)
            if arguments["--starteventid"]:
                self.start_event_id = int(arguments["--starteventid"])
            if arguments["--submit"]:
                self.submit = True
            if arguments["--no-ask"]:
                self.ask = False

            if arguments['DBFILE']:
                self.db_path = arguments['DBFILE']

            self.processing_func = self.parse_db

        home_dir = expanduser("~")
        config_file = join(home_dir, ".timy.conf")
        with open(config_file, "r") as config_json:
            d = json.load(config_json)
            self.redmine_api_access_key = d["api_key"]
            self.redmine = Redmine('https://tracker.endocode.com', key=self.redmine_api_access_key)

            try:
                self.contract_hours = float(d["contract_hours"])
            except KeyError:
                self.contract_hours = 40.0

            # load the mappings from the config file
            if not arguments['list']:
                self.task_project_mapping = d["task_project_mapping"]
                self.task_activity_mapping = d["task_activity_mapping"]
                try:
                    self.task_issue_mapping = d["task_issue_mapping"]
                except KeyError:
                    self.task_issue_mapping = {}

            if arguments['trackdb'] and not self.db_path:
                try:
                    self.db_path = d["db_path"]
                except KeyError:
                    sys.exit(3)

            self.project_cache = {}
            self.time_tracks = []

    def __cache_project(self, task_id):
        try:
            tracker_project_id = self.task_project_mapping[str(task_id)]
            self.project_cache[str(task_id)] = self.redmine.project.get(tracker_project_id)
        except KeyError:
            print("no project mapping for task {}".format(task_id))
            sys.exit(1)

    def __cache_activities(self):
        self.activities_map = {}
        for activity in self.redmine.enumeration.filter(resource='time_entry_activities'):
            self.activities_map[activity.id] = activity.name

    def parse_db(self):
        import sqlite3
        self.__cache_activities()

        con = sqlite3.connect(self.db_path)

        with con:
            con.row_factory = sqlite3.Row

            cur = con.cursor()

            query = 'SELECT * FROM Events WHERE (event_id) >= (?)'
            var_tup = (self.start_event_id, )

            if self.start_from_date:
                query += " AND (start) >= date(?)"
                var_tup += (datetime.strftime(self.start_from_date, cmdlinedate_fmt), )

            if self.end_at_date:
                query += " AND (start) <= date(?)"
                var_tup += (datetime.strftime(self.end_at_date, cmdlinedate_fmt), )

            cur.execute(query, var_tup)

            while True:
                row = cur.fetchone()

                if row == None:
                    break

                task_id = row['task']
                event_id = row['event_id']
                # Sometimes milliseconds are included in the timestamps. 
                # Remove them as they are not used anyway.
                start_date = datetime.strptime(row['start'].replace(".000", ""), sqlite_date_fmt)
                end_date = datetime.strptime(row['end'].replace(".000", ""), sqlite_date_fmt)
                comment = row['comment']
                self.__process_event(event_id, task_id, start_date, end_date, comment)

    def parse_xml(self):
        import xml.etree.ElementTree as ET
        self.__cache_activities()
        for event, elem in ET.iterparse(self.xml_export_path):
            if elem.tag == "event":
                task_id = int(elem.attrib["taskid"])
                event_id = int(elem.attrib["eventid"])
                start_date = datetime.strptime(elem.attrib['start'], datetime_fmt)
                end_date = datetime.strptime(elem.attrib['end'], datetime_fmt)
                comment = elem.text
                if comment:
                    comment = comment.strip()

                self.__process_event(event_id, task_id, start_date, end_date, comment)

    def __process_event(self, event_id, task_id, start_date, end_date, comment):
            if event_id < self.start_event_id:
                return
            if self.start_from_date and start_date < self.start_from_date:
                return
            if self.end_at_date and start_date > self.end_at_date:
                return

            # Look up project
            try:
                self.project_cache[str(task_id)]
            except KeyError:
                self.__cache_project(task_id)

            project = self.project_cache[str(task_id)]

            td = end_date - start_date
            dec_hours = td.seconds/60.0/60.0
            time_entry = self.redmine.time_entry.new()
            time_entry.project_id = project.id
            time_entry.spent_on = start_date.date()

            # Look up activity
            try:
                activity_id = self.task_activity_mapping[str(task_id)]
                time_entry.activity_id = activity_id
            except KeyError:
                print("No activity id for taskid {}".format(task_id))
                sys.exit(2)

            # Look up redmine issue id
            try:
                time_entry.issue_id = self.task_issue_mapping[str(task_id)]
            except KeyError:
                pass

            print("-"*50)
            print("Date:\t\t{}".format(datetime.strftime(start_date, "%Y-%m-%d")))
            print("Project:\t{}".format(project.name))
            try:
                activity = self.activities_map[activity_id]
            except KeyError:
                activity = activity_id
            print("Activity:\t{}".format(activity))

            if time_entry.issue_id:
                try:
                    issue_subject = self.redmine.issue.get(time_entry.issue_id).subject
                except ResourceSetIndexError:
                    print("invalid issue id {}".format(time_entry.issue_id))
                    sys.exit(1)
            else:
                issue_subject = "No issue"
            print("Issue:\t\t{}, id: {}".format(issue_subject, time_entry.issue_id))
            rounded_dec_hours = float("{0:.2f}".format(dec_hours))
            print("Spent time:\t{}\tdecimal: {}".format(td,rounded_dec_hours))
            time_entry.hours = rounded_dec_hours
            if not comment:
                comment = ""
            print("Comments:\t{}".format(comment))
            time_entry.comments = comment
            print("Event id:\t#{}".format(event_id))
            if self.submit:
                if self.ask:
                    answer = input("Submit?")
                    if not answer.lower() in ["y", "yes"]:
                        return
                try:
                    time_entry.save()
                except ValidationError as e:
                    print("Could not save the time entry #{} because [{}]".format(event_id, e))
                    sys.exit(4)

    def print_all_projects(self):
        print("#Project ID\t-\tProject Name".format())
        print("="*80)
        for project in self.redmine.project.all():
            print("#{}\t\t-\t{}".format(project.id, project.name))

    def print_all_users(self):
        print("#User ID\t-\tName".format())
        print("="*80)
        for user in self.redmine.user.all():
            print("#{}\t\t-\t{} {}".format(user.id, user.firstname, user.lastname))

    def print_activity_ids(self):
        for activity in self.redmine.enumeration.filter(resource='time_entry_activities'):
            print(activity.id, activity.name)

    def print_time_tracks_from(self):
        summarized_hours = 0

        current_user = self.redmine.user.get(self.user)
        print("Time tracks for user {} {}".format(current_user.firstname, current_user.lastname))
        time_entries = self.redmine.time_entry.all(user_id=current_user.id, sort="spent_on", from_date=self.start_from_date, to_date=self.end_at_date)

        try:
            self.current_day = time_entries[0].spent_on
        except ResourceSetIndexError:
            print("Unable to retrive time tracks from {} to {}".format(self.start_from_date, self.end_at_date))
            return

        self.day_hours = 0.0

        for te in time_entries:
            if self.verbose and self.sumday and te.spent_on > self.current_day:
                self.print_daily_totals()
                self.next_day(te.spent_on)

            summarized_hours += te.hours
            if self.sumday:
                self.day_hours += te.hours
            if self.verbose:
                if not "comments" in dir(te):
                    te.comments = ""
                print("{} spent {} {} hours on {} - {}".format(te.spent_on, te.hours, te.activity, te.project, te.comments))

        # sum up on last time entry
        if self.day_hours > 0.0 and self.verbose:
            self.print_daily_totals()

        if self.end_at_date:
            to_day = self.end_at_date
        else:
            to_day = date.today()

        work_days = numpy.busday_count(self.start_from_date, to_day + timedelta(days = 1))
        required_hours = work_days * (self.contract_hours / 5)
        if self.verbose:
            print("total {:.2f} hours / required {} hours".format(summarized_hours, required_hours))
        print("balance: {:.2f} hours (since: {} # working days: {})".format(summarized_hours - required_hours, self.start_from_date, work_days))

    def next_day(self, date):
        self.current_day = date
        self.day_hours = 0.0

    def print_daily_totals(self):
        print("{} totals {:.2f} hours\n".format(self.current_day, self.day_hours))

def main():
    arguments = docopt.docopt(__doc__, version='Timy 0.4')
    ctt = CharmTimeTracking(arguments)
    ctt.processing_func()

if __name__ == "__main__":
    main()
