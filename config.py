import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    guild_ids = json.loads(os.getenv("guild_ids"))
    serviceKey = os.getenv("serviceKey")
    aws_access_key_id = os.getenv("AWS_ID")
    aws_secret_access_key = os.getenv("AWS_KEY")
    region_name = os.getenv("REGION")

    SERVER_URL = "https://iosif.dev"

    ENDPOINTS = {"FILES": "/files"}

    DISCORD_API_V9 = "https://discord.com/api/v9"

    keywords = {
        "^오^": "/teemo.mp3",
        "비둘기": "/pigeon.mp3",
        "네이스": "/nayce.mp3",
        "기모링": "/gimoring.mp3",
        "무야호": "/muyaho.mp3",
        "muyaho": "/myh.mp3",
        "ㅃ!": "/byebye.mp3",
        "ㅂ!": "/bye.mp3",
        "안물": "/anmul.mp3",
        "애옹": "/meow.mp3",
    }

    voices = {
        " ": "Seoyeon",
        "t": "Takumi",
        "m": "Matthew",
        "f": "Filiz",
        "e": "Enrique",
        "s": "Seoyeon",
        "р": "Tatyana",
    }

    prefix = ";"
    volume_tts = 0.07
    volume_music = 0.10

    status_messages = ["😼", "eong", "😺", "😻", "😾", "🙀", "🐈", "😹", "애옹"]


def getLogger():
    Log_Format = "%(levelname)s %(asctime)s - %(message)s"
    logging.basicConfig(filename="eong.log", filemode="w", format=Log_Format, level=logging.INFO)

    return logging.getLogger()
