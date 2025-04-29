import asyncio
import subprocess
import sys
import os
from dotenv import load_dotenv

load_dotenv()

required_vars = ['MAIN_BOT_TOKEN', 'SUB_BOT_TOKEN']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please create a .env file with the required variables.")
    print("See .env.example for reference.")
    sys.exit(1)

async def run_main_bot():
    process = await asyncio.create_subprocess_exec(
        sys.executable, 'main_bot.py', '--subprocess',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    print("Main bot started")
    return process

async def run_sub_bot():
    process = await asyncio.create_subprocess_exec(
        sys.executable, 'sub_bot.py', '--subprocess',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    print("Subscription bot started")
    return process

async def main():
    from database import init_db
    await init_db()
    print("Database initialized")

    main_bot = await run_main_bot()
    sub_bot = await run_sub_bot()
    
    try:
        await asyncio.gather(
            main_bot.wait(),
            sub_bot.wait()
        )
    except KeyboardInterrupt:
        print("Shutting down bots...")
        main_bot.terminate()
        sub_bot.terminate()
        await asyncio.gather(
            main_bot.wait(),
            sub_bot.wait()
        )
        print("Bots shut down successfully")

if __name__ == '__main__':
    asyncio.run(main()) 