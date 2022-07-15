import os

from bots.mainbot import MainBot as Main

import config

logger = config.getLogger()


if __name__ == "__main__":
    main = Main()
    main.run(os.getenv("TOKEN"))
