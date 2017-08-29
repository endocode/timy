# Timy

Welcome Redmine time trackers the time has come for you to not ever manually enter time tracks if you use the charm time tracker. Because there is no good in doing the same thing twice or use webapps or do anything manually.

## Install timy

1. Install via pip
- into virtual env:

      $ virtualenv -p python3 timy.env
      $ source timy.env/bin/activate
      $ pip install git+https://github.com/endocode/timy.git

- or system-wide:

      $ sudo pip3 install git+https://github.com/endocode/timy.git

- or user-wide:

      $ pip3 install --user git+https://github.com/endocode/timy.git

2. create your configuration

  Timy will look for a configuration file in `$HOME/.timy.conf` that must be valid JSON and look like this:

        {
        "api_key": "<Your Redmine API-Key>",
        "task_project_mapping": {
            "<a CHARM TASK ID>": <corresponding Redmine Project ID>,
            "<a 2nd CHARM TASK ID>": <corresponding Redmine Project ID>
        },
        "task_activity_mapping" : {
            "<a CHARM TASK ID>": <corresponding Redmine activity ID>,
            "<a 2nd CHARM TASK ID>": <corresponding Redmine activity ID>
        },
        "db_path": "/home/<username>/.local/share/KDAB/Charm/Charm.db"
        }

    HINT: You can obtain the the Redmine Project/activity ids via timy. Just place the api key in the configuration and

    `$ timy list projects`

    and

    `$ timy list activities`

    there is also a sample `config.json.example` for you.

5. See what timy can do for you `timy -h`
6. **BE WARNED:** If you screw up your time tracks **it is all your fault!** **THERE IS NO DUPLICATE DETECTION!!**
7. Track times:
      - from XML `./track_charm.py trackxml <XMLEXPORT>`
      - or directly `./track_charm.py trackdb`
8. Yes only with `-S` tracks are submitted. **I told you to read the help!**
