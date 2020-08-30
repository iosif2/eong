from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import os
from tempfile import gettempdir
import json
import discord


def tts(txt):
    with open('credentials.json') as f:
        credentials = json.load(f)

        session = Session(aws_access_key_id=credentials['aws_access_key_id'],
                          aws_secret_access_key=credentials['aws_secret_access_key'],
                          region_name=credentials['region_name'])
    polly = session.client("polly")
    try:
        response = polly.synthesize_speech(Text=txt, OutputFormat="mp3",
                                           VoiceId="Seoyeon")
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
    return discord.PCMVolumeTransformer(original=discord.FFmpegPCMAudio(output), volume=0.5)
