import json
import os
import logging
from dotenv import load_dotenv
load_dotenv()


class Config:
    guild_ids = json.loads(os.getenv('guild_ids'))
    serviceKey = os.getenv('serviceKey')

    SERVER_URL = 'https://iosif.app'
    ENDPOINTS = {
        'FILES': '/files'
    }

    keywords = {
        '^오^': '/teemo.mp3',
        '비둘기': '/pigeon.mp3',
        '네이스': '/nayce.mp3',
        '기모링': '/gimoring.mp3',
        '빡빡이': '/bald.mp3',
        '무야호': '/muyaho.mp3',
        '시옹포포': '/sop.mp3',
        'muyaho': '/myh.mp3',
        'ㅇㅈㅇㅈㅎㄴ': '/dizzy.mp3',
        '🖕': '/fy.mp3',
        'ㅃ!': '/byebye.mp3',
        'ㅂ!': '/bye.mp3',
        '안물': '/anmul.mp3',
        '애옹': '/meow.mp3',
        '음?': '/wdis.mp3',
        '대치동': '/daechi.mp3'
    }

    voices = {
        't': 'Takumi',
        'm': 'Matthew',
        'f': 'Filiz',
        'e': 'Enrique',
        'z': 'Zeina',
        'l': 'Lotte',
        's': 'Seoyeon',
        'р': 'Tatyana'
    }

    prefix = ';'

    volume = 0.05

    status_messages = ['😼', 'eong', '😺', '😻', '😾', '🙀', '🐈', '😹', '애옹']

    def getLogger():
        Log_Format = "%(levelname)s %(asctime)s - %(message)s"
        logging.basicConfig(filename="eong.log",
                            filemode="a",
                            format=Log_Format,
                            level=logging.INFO)

        return logging.getLogger()
