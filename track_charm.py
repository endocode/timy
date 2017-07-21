#!/usr/bin/env python

"""Charm2RedmineTT

Usage:
  track_charm.py list projects
  track_charm.py list activities
  track_charm.py list timetracks [--verbose | -v] [--days=<days> | --startdate=<start_date>] [--enddate=<end_date>] [--sumday]
  track_charm.py track <EXPORTFILE> [--submit|-S] [--starteventid=<event_id>] [--startdate=<start_date>] [--enddate=<end_date>] [--ask | -a]
  track_charm.py (-h | --help)
  track_charm.py --version

Options:
  -h --help                     Show this screen.
  --version                     Show version.
  -v --verbose                  Print more information.
  --starteventid=<event_id>     Skip events before event_id.
  --startdate=<start_date>      Skip events before start_date (YYYY-MM-DD)
  --enddate=<end_date>          Skip events after end_date (YYYY-MM-DD)
  -S --submit                   Actually create time tracks in Redmine.
  -a --ask                      Ask before submitting a time track.
  --days=<days>                 Print time tracks for the last <days> otherwise print current month

"""

from redminelib import Redmine
from datetime import date, timedelta, datetime
import numpy
import json
import xml.etree.ElementTree as ET
import docopt

datetime_fmt = "%Y-%m-%dT%H:%M:%SZ"
cmdlinedate_fmt = "%Y-%m-%d"
almost_a_day = 86399

class CharmTimeTracking(object):

    def __init__(self):
        with open("./config.json", "r") as config_json:
            d = json.load(config_json)
            self.redmine_api_access_key = d["api_key"]
            self.redmine = Redmine('https://tracker.endocode.com', key=self.redmine_api_access_key)
            self.task_project_mapping = d["task_project_mapping"]
            self.task_activity_mapping = d["task_activity_mapping"]
            self.project_cache = {}
            self.time_tracks = []

    def __cache_project(self, task_id):
        try:
            tracker_project_id = self.task_project_mapping[task_id]
            self.project_cache[task_id] = self.redmine.project.get(tracker_project_id)
        except KeyError:
            print("Dafuq no mapping for task {}".format(elem.attrib["taskid"]))
            sys.exit(1)

    def __cache_activities(self):
        self.activities_map = {}
        for activity in self.redmine.enumeration.filter(resource='time_entry_activities'):
            self.activities_map[activity.id] = activity.name

    def parse_xml(self, source, submit=False, ask=False, start_from_date=None, end_at_date=None, start_event_id=1):
        self.__cache_activities()

        for event, elem in ET.iterparse(source):
            if elem.tag == "event" and int(elem.attrib["eventid"]) > start_event_id:
                task_id = elem.attrib["taskid"]
                event_id = elem.attrib["eventid"]
                start_date = datetime.strptime(elem.attrib['start'], datetime_fmt)
                if start_from_date and start_date < start_from_date:
                    continue
                if end_at_date and start_date > end_at_date:
                    continue
                end_date = datetime.strptime(elem.attrib['end'], datetime_fmt)
                comment = elem.text
                if comment:
                    comment = comment.strip()
                try:
                    self.project_cache[task_id]
                except KeyError:
                    self.__cache_project(task_id)

                project = self.project_cache[task_id]
                td = end_date - start_date
                dec_hours = td.seconds/60.0/60.0
                time_entry = self.redmine.time_entry.new()
                time_entry.project_id = project.id
                time_entry.spent_on = start_date.date()
                try:
                    activity_id = self.task_activity_mapping[task_id]
                    time_entry.activity_id = activity_id
                except KeyError:
                    print("No activity id for taskid {}".format(task_id))
                    sys.exit(2)
                print("-"*50)
                print("Date:\t\t{}".format(datetime.strftime(start_date, "%Y-%m-%d")))
                print("Project:\t{}".format(project.name))
                try:
                    activity = self.activities_map[activity_id]
                except KeyError:
                    activity = activity_id
                print("Activity:\t{}".format(activity))
                rounded_dec_hours = float("{0:.2f}".format(dec_hours))
                print("Spent time:\t{}\tdecimal: {}".format(td,rounded_dec_hours))
                time_entry.hours = rounded_dec_hours
                if not comment:
                    comment = ""
                print("Comments:\t{}".format(comment))
                time_entry.comments = comment
                print("Event id:\t#{}".format(event_id))
                if submit:
                    if ask:
                        answer = input("Submit?")
                        if not answer.lower() in ["y", "yes"]:
                            continue
                    time_entry.save()

    def print_all_projects(self):
        print("#Project ID\t-\tProject Name".format())
        print("="*80)
        for project in self.redmine.project.all():
            print("#{}\t\t-\t{}".format(project.id, project.name))

    def print_activity_ids(self):
        for activity in self.redmine.enumeration.filter(resource='time_entry_activities'):
            print(activity.id, activity.name)

    def get_time_tracks_from(self, dates):
        current_user = self.redmine.user.get('current')
        print(dates)

        time_entries = self.redmine.time_entry.all(user_id=current_user.id, sort="spent_on", **dates)
        return time_entries

    def print_time_tracks_from(self, dates, to_date=None, verbose=False, sumday=False):
        summarized_hours = 0
        if not dates["from_date"]:
            return

        from_date = dates["from_date"]

        time_entries = self.get_time_tracks_from({k:v for k,v in dates.items() if k.endswith("_date")})

        self.current_day = time_entries[0].spent_on
        self.day_hours = 0.0

        for te in time_entries:
            if verbose and sumday and te.spent_on > self.current_day:
                self.print_daily_totals()
                self.next_day(te.spent_on)

            summarized_hours += te.hours
            self.day_hours += te.hours
            if verbose:
                if not "comments" in dir(te):
                    te.comments = ""
                print("{} spent {} {} hours on {} - {}".format(te.spent_on, te.hours, te.activity, te.project, te.comments))

        # sum up on last time entry
        if self.day_hours > 0.0:
            self.print_daily_totals()

        if dates["to_date"]:
            to_day = dates["to_date"]
        else:
            to_day = date.today()
        work_days = numpy.busday_count(from_date, to_day + timedelta(days = 1))
        required_hours = work_days * 8.0
        if verbose:
            print("total {:.2f} hours / required {} hours".format(summarized_hours, required_hours))
        print("balance: {:.2f} hours (since: {} # working days: {})".format(summarized_hours - required_hours, from_date, work_days))

    def next_day(self, date):
        self.current_day = date
        self.day_hours = 0.0

    def print_daily_totals(self):
        print("{} totals {:.2f} hours".format(self.current_day, self.day_hours))


def main(arguments):
    ctt = CharmTimeTracking()
    if arguments['list'] and arguments['projects']:
        ctt.print_all_projects()

    if arguments['list'] and arguments['activities']:
        ctt.print_activity_ids()

    if arguments['list'] and arguments['timetracks']:
        dates = {}
        if arguments["--days"]:
            dates["from_date"] = date.today() - timedelta(days=int(arguments["--days"]))
        else:
            if arguments["--startdate"]:
                dates["from_date"] = datetime.strptime(arguments["--startdate"], cmdlinedate_fmt).date()
            else:
                dates["from_date"] = date.today().replace(day=1)
        if arguments["--enddate"]:
            dates["to_date"] = datetime.strptime(arguments["--enddate"], cmdlinedate_fmt).date()
        kwargs = {}
        kwargs["verbose"] = arguments["--verbose"]
        kwargs["sumday"] = arguments["--sumday"]
        ctt.print_time_tracks_from(dates, **kwargs)

    if arguments['track'] and arguments['<EXPORTFILE>']:
        kwargs = {}
        if arguments["--startdate"]:
            kwargs["start_from_date"] = datetime.strptime(arguments["--startdate"], cmdlinedate_fmt)
        if arguments["--enddate"]:
            kwargs["end_at_date"] = datetime.strptime(arguments["--enddate"], cmdlinedate_fmt) + timedelta(seconds=almost_a_day)
        if arguments["--starteventid"]:
            kwargs["start_event_id"] = int(arguments["--starteventid"])
        kwargs["submit"] = arguments["--submit"]
        kwargs["ask"] = arguments["--ask"]
        ctt.parse_xml(arguments["<EXPORTFILE>"], **kwargs)

if __name__ == "__main__":
    arguments = docopt.docopt(__doc__, version='Charm2RedmineTT 0.1')
    main(arguments)
