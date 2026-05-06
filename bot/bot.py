"""
MindPilot QQ Bot - NoneBot2 Entry Point

Usage:
    1. Install: pip install nonebot2 nonebot-adapter-onebot
    2. Set environment variables in .env
    3. Run: python bot.py
"""
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

# Initialize NoneBot
nonebot.init()

# Register OneBot adapter
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# Load plugins
nonebot.load_plugins("plugins")

if __name__ == "__main__":
    nonebot.run()
