import os

import config
from bots.mainbot import MainBot as Main

logger = config.getLogger()


if __name__ == "__main__":
    main = Main()
    main.run(os.getenv('TOKEN'))
