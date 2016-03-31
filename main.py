from redmine import Redmine
from datetime import date
import json

class TimeTrack(object):

    def __init__(self):
        with open("./config.json", "r") as config_json:
            d = json.load(config_json)
            self.redmine_api_access_key = d["api_key"]
            self.redmine = Redmine('https://tracker.endocode.com', key=self.redmine_api_access_key)

    def get_time_tracks_from(self, from_date):
        current_user = self.redmine.user.get('current')

        time_entries = self.redmine.time_entry.all(limit=100, user_id=current_user.id, from_date=from_date)
        return time_entries

    def print_time_tracks_from(self, from_date):
        summarized_hours = 0

        time_entries = self.get_time_tracks_from(from_date)

        for te in time_entries:
            summarized_hours += te.hours
            print("{} spent on {}".format(te.hours, te.spent_on))

        print("total {} hours".format(summarized_hours))


if __name__ == "__main__":
    first_of_month = date.today().replace(day=1)

    timetracker = TimeTrack()
    timetracker.print_time_tracks_from(first_of_month)

