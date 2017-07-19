#!/usr/bin/env python
from redminelib import Redmine
from datetime import date, timedelta
import constants
import numpy
import json

class TimeTrack(object):

    def __init__(self):
        with open("./config.json", "r") as config_json:
            d = json.load(config_json)
            self.redmine_api_access_key = d["api_key"]
            self.redmine = Redmine('https://tracker.endocode.com', key=self.redmine_api_access_key)

    def get_time_tracks_from(self, from_date):
        current_user = self.redmine.user.get('current')

        time_entries = self.redmine.time_entry.all(user_id=current_user.id, from_date=from_date)
        return time_entries

    def print_time_tracks_from(self, from_date):
        summarized_hours = 0

        time_entries = self.get_time_tracks_from(from_date)

        for te in time_entries:
            summarized_hours += te.hours
            if constants.VERBOSE:
                print("{} spent on {}".format(te.hours, te.spent_on))

        if constants.VERBOSE:
            print("total {} hours".format(summarized_hours))

        today = date.today()
        days = numpy.busday_count(from_date, today + timedelta(days = 1))

        print("balance: {} hours (since: {})".format(summarized_hours - days * 8.0, from_date))


if __name__ == "__main__":
    first_of_month = date.today().replace(day=1)
    first_of_year = date.today().replace(day=1, month=1)


    timetracker = TimeTrack()
    timetracker.print_time_tracks_from(first_of_month)
    timetracker.print_time_tracks_from(first_of_year)

