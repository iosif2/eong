from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import os
from tempfile import gettempdir
import json
import discord
from dotenv import load_dotenv

load_dotenv()


def tts(txt, speaker):
    session = Session(aws_access_key_id=os.getenv('AWS_ID'), aws_secret_access_key=os.getenv('AWS_KEY'),
                      region_name=os.getenv('REGION'))
    polly = session.client("polly")
    try:
        response = polly.synthesize_speech(Text=txt, OutputFormat="mp3",
                                           VoiceId=speaker)
    except (BotoCoreError, ClientError) as error:
        print(error)
        return None
    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            output = os.path.join(gettempdir(), "speech.mp3")
            try:
                with open(output, "wb") as file:
                    file.write(stream.read())
            except IOError as error:
                print(error)
                return None
    else:
        print("Could not stream audio")
        return None
    return output
