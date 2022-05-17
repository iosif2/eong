# eong
[![python](https://img.shields.io/badge/python-3.9-blue)](https://www.python.org/)
[![GitHub](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)

## Intro
eong is discord bot made by iosif

### Required environment variables
```json
"TOKEN": "Discord bot token for main bot"
"TOKEN": "Discord bot token for music bot"
"AWS_ID": "AWS ID for AWS Amazon polly"
"AWS_KEY": "AWS Key for AWS Amazon polly"
"REGION": "AWS Region"
"guild_ids": "Server IDs for slash commands"
"serviceKey": "serviceKey for OPENAPI-COVID_19" [deprecated]
```

### How to
```bash
python3 -m venv venv # make new python virtualenv
source venv/bin/activate # for mac&linux
# venv/Scripts/activate.cmd # for Windows
pip install -r requirements.txt # install required python packages
python main.py # run
```
