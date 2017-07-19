#!/usr/bin/env python

"""Charm2RedmineTT

Usage:
  track_charm.py list projects
  track_charm.py list activities
  track_charm.py list timetracks [--verbose | -v] [--days=<days>]
  track_charm.py track <EXPORTFILE> [--no-dry-run|-f] [--last_event_id=<event_id>] [--ask | -a]
  track_charm.py (-h | --help)
  track_charm.py --version

Options:
  -h --help                     Show this screen.
  --version                     Show version.
  -v --verbose                  Print more information.
  --last_event_id=<event_id>    Skip events until (including) event_id.
  -f --no-dry-run               Actually create time tracks in Redmine.
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

class CharmTimeTracking(object):

    def __init__(self):
        with open("./config.json", "r") as config_json:
            d = json.load(config_json)
            self.redmine_api_access_key = d["api_key"]
            self.redmine = Redmine('https://tracker.endocode.com', key=self.redmine_api_access_key)
            self.task_project_mapping = d["task_project_mapping"]
            self.task_activity_mapping = d["task_activity_mapping"]
            self.last_event_no = d["last_event_no"]
            self.project_cache = {}
            self.time_tracks = []

    def cache_project(self, task_id):
        try:
            tracker_project_id = self.task_project_mapping[task_id]
            self.project_cache[task_id] = self.redmine.project.get(tracker_project_id)
        except KeyError:
            print("Dafuq no mapping for task {}".format(elem.attrib["taskid"]))
            sys.exit(1)


    def parse_xml(self, source, save=False, ask=False, last_event_id=None):
        if not last_event_id:
            last_event_id = self.last_event_no
        for event, elem in ET.iterparse(source):
            if elem.tag == "event" and int(elem.attrib["eventid"]) > last_event_id:
                task_id = elem.attrib["taskid"]
                event_id = elem.attrib["eventid"]
                comment = elem.text
                if comment:
                    comment = comment.strip()
                try:
                    self.project_cache[task_id]
                except KeyError:
                    self.cache_project(task_id)

                project = self.project_cache[task_id]
                start_date = datetime.strptime(elem.attrib['start'], datetime_fmt)
                end_date = datetime.strptime(elem.attrib['end'], datetime_fmt)
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
                print("-"*30)
                print(datetime.strftime(start_date, "%Y-%m-%d"))
                print(project.name)
                print("Activity: {}".format(activity_id))
                print(td)

                rounded_dec_hours = float("{0:.2f}".format(dec_hours))
                time_entry.hours = rounded_dec_hours
                print(rounded_dec_hours)
                if not comment:
                    comment = ""
                print(comment)
                time_entry.comments = comment
                print("Event id #{}".format(event_id))
                if save:
                    if ask:
                        answer = input("Submit?")
                        if not answer.lower() in ["y", "yes"]:
                            continue
                    time_entry.save()
                else:
                    self.time_tracks.add(time_entry)


    def print_all_projects(self):
        print("#Project ID\t-\tProject Name".format())
        print("="*80)
        for project in self.redmine.project.all():
            print("#{}\t\t-\t{}".format(project.id, project.name))

    def print_activity_ids(self):
        for activity in self.redmine.enumeration.filter(resource='time_entry_activities'):
            print(activity.id, activity.name)

    def get_time_tracks_from(self, from_date):
        current_user = self.redmine.user.get('current')

        time_entries = self.redmine.time_entry.all(user_id=current_user.id, from_date=from_date, sort="spent_on")
        return time_entries

    def print_time_tracks_from(self, from_date, verbose=False):
        summarized_hours = 0

        time_entries = self.get_time_tracks_from(from_date)

        for te in time_entries:
            summarized_hours += te.hours
            if verbose:
                if not "comments" in dir(te):
                    te.comments = ""
                print("{} spent {} {} hours on {} - {}".format(te.spent_on, te.hours, te.activity, te.project, te.comments))

        if verbose:
            print("total {0:.2f} hours".format(summarized_hours))

        today = date.today()
        days = numpy.busday_count(from_date, today + timedelta(days = 1))

        print("balance: {:.2f} hours (since: {})".format(summarized_hours - days * 8.0, from_date))


def main(arguments):
    ctt = CharmTimeTracking()
    if arguments['list'] and arguments['projects']:
        ctt.print_all_projects()
    if arguments['list'] and arguments['activities']:
        ctt.print_activity_ids()
    if arguments['list'] and arguments['timetracks']:
        if arguments["--days"]:
            from_date = date.today() - timedelta(days=int(arguments["--days"]))
        else:
            from_date = date.today().replace(day=1)
        ctt.print_time_tracks_from(from_date, arguments['--verbose'])
    if arguments['track'] and arguments['<EXPORTFILE>']:
        ctt.parse_xml(arguments["<EXPORTFILE>"], arguments["--no-dry-run"], arguments["--ask"], arguments["--last_event_id"])

if __name__ == "__main__":
    arguments = docopt.docopt(__doc__, version='Charm2RedmineTT 0.1')
    main(arguments)