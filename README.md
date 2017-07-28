# Timy

Welcome Redmine time trackers the time has come for you to not ever manually enter time tracks if you use the charm time tracker. Because there is no good in doing the same thing twice or use webapps or do anything manually.

All you need to do:

1. Create a Python3 virtualenv and populate with provided requirements.txt and activate it.
2. Export your charm time tracks to XML - *I don't know who came up with XML ;) (optional)
3. Copy provided `config.json.example` to `config.json` and adapt to your needs.

  Your needs are: your **redmine api key** and your **charm task ids** (get charm task ids from the xml export)
4. Get the needed project and activity id from tracker database

  If do not have access to the database use `./track_charm.py list projects` and `./track_charm.py list activities`
5. See what track_charm.py can do for you `./track_charm.py -h`
6. **BE WARNED:** If you screw up your time tracks **it is all your fault!** **THERE IS NO DUPLICATE DETECTION!!**
7. Track times
    from XML `./track_charm.py trackxml <XMLEXPORT>`
    or directly `./track_charm.py trackdb`
8. Yes only with `-S` tracks are submitted. **I told you to read the help!**
