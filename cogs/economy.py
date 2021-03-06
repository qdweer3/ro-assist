import discord
import aiohttp
import html
import time
import json
import asyncio

from discord.ext import commands, tasks
from database import db, cursor, get_guild, get_user, get_all_users, get_top10_users
from random import randint, random
from asyncio import TimeoutError
from typing import Optional
from math import ceil

XP_RATE = 200
DAILY_REWARD = 2000

JOBS = [
    {"name": "Janitor", "id": 0, "lvl_required": 5, "robux_payment": (1, 20), "message": "You earned {} robux by clearing building. :moneybag:"},
    {"name": "Miner", "id": 1, "lvl_required": 10, "robux_payment": (100, 200), "message": "You earned {} robux by mining coal. :moneybag:"},
    {"name": "Youtuber", "id": 2, "lvl_required": 20, "robux_payment": (500, 1000), "message": "You earned {} robux by recording videos. :moneybag:"},
    {"name": "ROBLOX Admin", "id": 3, "lvl_required": 25, "robux_payment": (1000, 3500), "message": "You earned {} robux by banning cheaters on ROBLOX. :moneybag:"},
    {"name": "Discord Admin", "id": 4, "lvl_required": 45, "robux_payment": (4500, 8600), "message": "You earned {} robux by banning 12 year old kids. :moneybag:"},
    {"name": "Businessman", "id": 5, "lvl_required": 200, "robux_payment": (100000, 200000), "message": "You earned {} robux by selling cars. :moneybag:"}
]

async def more_inventory_space(ctx, inventory):
    inventory.append(-1)
    return False

SHOP_ITEMS = [
    {"name": "Bloxy-Cola", "id": 0, "price": 50, "description": "Fresh Bloxy cola!"},
    {"name": "Gaming PC", "id": 1, "price": 20000, "description": "\"i gonna play fortnite\""},
    {"name": "PS5", "id": 2, "price": 80000, "description": "PlayStation 5!"},
    {"name": "Ban Hammer", "id": 3, "price": 1000000, "description": "The powerful ban hammer!"},
    {"name": "More inventory space", "id": 4, "price": 1000000, "description": "Adds 1 more space into your inventory.", "callback": more_inventory_space}
]

SHOP_ITEMS_PER_PAGE = 9
JOB_PER_PAGE = 9
INVENTORY_ITEMS_PER_PAGE = 9

def get_job_by_name(job_name):
    global JOBS

    for job in JOBS:
        if job["name"] == job_name:
            return job

def get_job_by_id(job_id):
    global JOBS

    for job in JOBS:
        if job["id"] == job_id:
            return job

def get_item_by_name(item_name):
    global SHOP_ITEMS

    for item in SHOP_ITEMS:
        if item["name"] == item_name:
            return item

def get_item_by_id(item_id):
    global SHOP_ITEMS

    for item in SHOP_ITEMS:
        if item["id"] == item_id:
            return item

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.tradingUsers = []

    async def check_exp(self, user, message):
        if user[2] >= (user[1] * XP_RATE):
            level_to_add = 1
            exp_left = user[2] - (user[1] * XP_RATE)
            level = user[1] + 1

            while (exp_left >= (level * XP_RATE)):
                level_to_add += 1
                exp_left -= (level * XP_RATE)
                level += 1

            cursor.execute(f"UPDATE users SET exp = 0, level = level + {level_to_add} WHERE user_id = %s", (message.author.id,))
            db.commit()

    async def give_exp(self, user_id, exp, message):
        cursor.execute(f"UPDATE users SET exp = exp + {exp} WHERE user_id = %s", (user_id,))
        db.commit()
        await self.check_exp(get_user(user_id), message)

    def give_robux(self, user_id, robux):
        cursor.execute(f"UPDATE users SET robux = robux + {robux} WHERE user_id = %s", (user_id,))
        db.commit()

    def remove_robux(self, user_id, robux):
        cursor.execute(f"UPDATE users SET robux = robux - {robux} WHERE user_id = %s", (user_id,))
        db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or isinstance(message.channel, discord.DMChannel):
            return

        guild = get_guild(message.guild.id)
        if not message.content.startswith(guild[1]) and random() <= 0.50:
            await self.give_exp(message.author.id, randint(1, 3), message)

    @commands.command(
        name = "earn-robux",
        description = "Earn robux"
    )
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def earn_robux(self, ctx):
        robux = randint(0, 10)

        if robux > 0:
            self.give_robux(ctx.author.id, robux)

            embed = discord.Embed(title = "Earn Robux", description = f"You earnt {robux} robux.", colour = discord.Colour.green())
            embed.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            await ctx.send(embed = embed)
        else:
            embed = discord.Embed(title = "Earn Robux", description = "You didn't earn anything, sadly :(", colour = discord.Colour.red())
            embed.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            await ctx.send(embed = embed)

    @commands.command(
        description = "Shows your current stats (exp, level, robux, etc.)"
    )
    async def stats(self, ctx):
        user = get_user(ctx.author.id)

        embed_stats = discord.Embed(title = "Stats", colour = discord.Colour.green())
        embed_stats.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))
        embed_stats.add_field(name = "Level", value = user[1])
        embed_stats.add_field(name = "Exp", value = f"{user[2]}/{user[1] * XP_RATE}")
        embed_stats.add_field(name = "Robux", value = user[3])

        await ctx.send(embed = embed_stats)

    @commands.command(
        name = "level-leaderboard",
        description = "Shows top 10 users by level"
    )
    async def level_leaderboard(self, ctx):
        users = get_top10_users("exp", 10)

        if len(users) == 0:
            embed_failure = discord.Embed(title = "Level Leaderboard", description = "Leaderboard is empty.", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        leaderboard = "```"
        count = 1
        for i in range(len(users)):
            user = self.bot.get_user(users[i][0])

            if user:
                leaderboard += f"{count}. {user} - {users[i][1]} level\n"
                count += 1
        leaderboard += "```"

        await ctx.send(embed = discord.Embed(title = "Level Leaderboard", description = leaderboard, colour = discord.Colour.green()))

    @commands.command(
        name = "exp-leaderboard",
        description = "Shows top 10 users by exp"
    )
    async def exp_leaderboard(self, ctx):
        users = get_top10_users("exp", 10)

        if len(users) == 0:
            embed_failure = discord.Embed(title = "Exp Leaderboard", description = "Leaderboard is empty.", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        leaderboard = "```"
        count = 1
        for i in range(len(users)):
            user = self.bot.get_user(users[i][0])

            if user:
                leaderboard += f"{count}. {user} - {users[i][2]} exp\n"
                count += 1
        leaderboard += "```"

        await ctx.send(embed = discord.Embed(title = "Exp Leaderboard", description = leaderboard, colour = discord.Colour.green()))

    @commands.command(
        name = "robux-leaderboard",
        description = "Shows top 10 users by robux"
    )
    async def robux_leaderboard(self, ctx):
        users = get_top10_users("exp", 10)

        if len(users) == 0:
            embed_failure = discord.Embed(title = "Robux Leaderboard", description = "Leaderboard is empty.", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        leaderboard = "```"
        count = 1
        for i in range(len(users)):
            user = self.bot.get_user(users[i][0])

            if user:
                leaderboard += f"{count}. {user} - {users[i][3]} robux\n"
                count += 1
        leaderboard += "```"

        await ctx.send(embed = discord.Embed(title = "Robux Leaderboard", description = leaderboard, colour = discord.Colour.green()))

    @commands.command(
        description = "Earn robux by completing the quiz (20-60 robux reward)"
    )
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def quiz(self, ctx):
        embed = discord.Embed(title = "Quiz", description = """
        Choose difficulty:
        :one: - Easy
        :two: - Medium:
        :three: - Hard
        (30 seconds to choose)
        """, colour = discord.Colour.blurple())
        embed.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        message = await ctx.send(embed = embed)
        await message.add_reaction("1??????")
        await message.add_reaction("2??????")
        await message.add_reaction("3??????")

        reaction, user = await self.bot.wait_for("reaction_add", timeout = 30.0, check = lambda reaction, user: reaction.message.id == message.id and user.id == ctx.author.id)

        difficulty = None
        reward = None

        if reaction.emoji == "1??????":
            difficulty = "easy"
            reward = 20
        elif reaction.emoji == "2??????":
            difficulty = "medium"
            reward = 40
        elif reaction.emoji == "3??????":
            difficulty = "hard"
            reward = 60
        else:
            return

        async with self.session.get(f"https://opentdb.com/api.php?amount=1&difficulty={difficulty}&type=multiple") as r:
            result = await r.json()
            question = html.unescape(result["results"][0]["question"])
            answers = result["results"][0]["incorrect_answers"]
            answers.insert(randint(0, 3), result["results"][0]["correct_answer"])

            embed_quiz = discord.Embed(title = "Quiz (30 seconds to answer)", description = f"{question}\n:one: - {answers[0]}\t:two: - {answers[1]}\n:three: - {answers[2]}\t:four: - {answers[3]}", colour = discord.Colour.blurple())
            embed_quiz.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            message = await ctx.send(embed = embed_quiz)
            await message.add_reaction("1??????")
            await message.add_reaction("2??????")
            await message.add_reaction("3??????")
            await message.add_reaction("4??????")

            reaction, user = await self.bot.wait_for("reaction_add", timeout = 30.0, check = lambda reaction, user: reaction.message.id == message.id and user.id == ctx.author.id)

            correct_answer = result["results"][0]["correct_answer"]
            answer_pos = None

            if reaction.emoji == "1??????":
                answer_pos = 0
            elif reaction.emoji == "2??????":
                answer_pos = 1
            elif reaction.emoji == "3??????":
                answer_pos = 2
            elif reaction.emoji == "4??????":
                answer_pos = 3
            else:
                return

            if answers[answer_pos] == correct_answer:
                self.give_robux(ctx.author.id, reward)

                embed_success = discord.Embed(title = "Quiz", description = f"Right answer! You earnt {reward} robux.", colour = discord.Colour.green())
                embed_success.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

                await ctx.send(embed = embed_success)
            else:
                embed_failure = discord.Embed(title = "Quiz", description = f"Wrong answer! The right answer was: \"{correct_answer}\". Good luck next time!", colour = discord.Colour.red())
                embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

                await ctx.send(embed = embed_failure)

    @quiz.error
    async def quizerror(self, ctx, error):
        if isinstance(error, TimeoutError):
            embed_failure = discord.Embed(title = "Quiz", description = "Time's up!", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            await ctx.send(embed = embed_failure)

    @commands.command(
        name = "guess-the-number",
        description = "Guess the number game (20-100 robux reward)"
    )
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def guess_the_number(self, ctx):
        embed = discord.Embed(title = "Guess The Number", description = """
Choose difficulty:
:one: - Easy
:two: - Medium:
:three: - Hard
(30 seconds to choose)
        """, colour = discord.Colour.blurple())
        embed.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        message = await ctx.send(embed = embed)
        await message.add_reaction("1??????")
        await message.add_reaction("2??????")
        await message.add_reaction("3??????")

        reaction, user = await self.bot.wait_for("reaction_add", timeout = 30.0, check = lambda reaction, user: reaction.message.id == message.id and user.id == ctx.author.id)

        r = None
        reward = None

        if reaction.emoji == "1??????":
            r = (1, 5)
            reward = 20
        elif reaction.emoji == "2??????":
            r = (1, 12)
            reward = 50
        elif reaction.emoji == "3??????":
            r = (1, 20)
            reward = 100
        else:
            return

        number = randint(*r)

        embed = discord.Embed(title = "Guess The Number", description = f"I picked the number between {r[0]}-{r[1]}. Try guessing it! Remember, you have 5 minutes to guess it.", colour = discord.Colour.green())
        embed.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))
        await ctx.send(embed = embed)

        message = await self.bot.wait_for("message", timeout = 500.0, check = lambda message: message.channel.id == ctx.channel.id and message.author == ctx.author)

        try:
            userNumber = int(message.content)
        except ValueError:
            embed_failure = discord.Embed(title = "Guess The Number", description = "Invalid number. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        if userNumber != number:
            embed_failure = discord.Embed(title = "Guess The Number", description = f"Wrong number. Valid number was {number}. Good luck next time!", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        self.give_robux(ctx.author.id, reward)
        embed_success = discord.Embed(title = "Guess The Number", description = f"You guessed the number, congratulations! You earnt {reward} robux.", colour = discord.Colour.green())
        embed_success.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        await ctx.send(embed = embed_success)

    @commands.command(
        description = "Pays robux to specific user",
        usage = "[member] [amount]"
    )
    async def pay(self, ctx, member: discord.Member, amount: int):
        if member.bot:
            embed_failure = discord.Embed(title = "Pay Robux", description = "You want to pay robux to bot, seriously? :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        if amount < 1:
            embed_failure = discord.Embed(title = "Pay Robux", description = "You can't pay less than 1 robux. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        user = get_user(ctx.author.id)

        if user[3] < amount:
            embed_failure = discord.Embed(title = "Pay Robux", description = "You don't have that amount of robux. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        self.remove_robux(ctx.author.id, amount)
        self.give_robux(member.id, amount)

        embed_success = discord.Embed(title = "Pay Robux", description = f"You paid {amount} robux to {member.mention}. :white_check_mark:", colour = discord.Colour.green())
        embed_success.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        await ctx.send(embed = embed_success)

    @commands.command(
        name = "job-list",
        description = "Display all available jobs",
        usage = "[page (default = 1)]"
    )
    async def joblist(self, ctx, page: int = 1):
        global JOBS

        embed_job_list = discord.Embed(title = "Job List", colour = discord.Colour.green())

        ln = len(JOBS)
        pages = ceil(ln / JOB_PER_PAGE)

        if page < 1 or page > pages:
            embed_failure = discord.Embed(title = "Shop", description = "Invalid page. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        embed_job_list.set_footer(text = f"Page: {page} / {pages}")

        r1 = (page - 1) * JOB_PER_PAGE
        r2 = page * JOB_PER_PAGE

        for i in range(r1, r2):
            job = JOBS[i]
            embed_job_list.add_field(name = f"`{job['name']}`", value = f"Level Required: {job['lvl_required']}. Payment: {job['robux_payment'][0]}-{job['robux_payment'][1]} robux", inline = False)

        await ctx.send(embed = embed_job_list)

    @commands.command(
        name = "go-to-job",
        description = "Get a job by using this command",
        usage = "[job_name]"
    )
    async def go_to_job(self, ctx, *, job_name):
        job = get_job_by_name(job_name)

        if job == None:
            embed_failure = discord.Embed(title = "Job", description = f"Invalid job name. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        user = get_user(ctx.author.id)

        if user[1] < job["lvl_required"]:
            embed_failure = discord.Embed(title = "Job", description = f"You need level {job['lvl_required']} to get this job. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        cursor.execute("UPDATE users SET job_id = %s WHERE user_id = %s", (job["id"], ctx.author.id,))
        db.commit()

        embed_success = discord.Embed(title = "Job", description = f"You are working as {job['name']} now. :white_check_mark:", colour = discord.Colour.green())
        embed_success.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        await ctx.send(embed = embed_success)

    @commands.command(
        description = "Work and earn robux"
    )
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def work(self, ctx):
        user = get_user(ctx.author.id)

        if user[5] == None:
            embed_failure = discord.Embed(title = "Job", description = f"You don't have a job. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        job = get_job_by_id(user[5])

        robux = randint(*job["robux_payment"])
        self.give_robux(ctx.author.id, robux)

        embed_success = discord.Embed(title = "Job", description = job["message"].format(robux), colour = discord.Colour.green())
        embed_success.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        await ctx.send(embed = embed_success)

    @commands.command(
        description = "Shows available items in shop",
        usage = "[page (default = 1)]"
    )
    async def shop(self, ctx, page: int = 1):
        embed_shop = discord.Embed(title = "Shop", colour = discord.Colour.green())

        pages = ceil(len(SHOP_ITEMS) / SHOP_ITEMS_PER_PAGE)

        if page < 1 or page > pages:
            embed_failure = discord.Embed(title = "Shop", description = "Invalid page. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        embed_shop.set_footer(text = f"Page: {page} / {pages}")

        r1 = (page - 1) * SHOP_ITEMS_PER_PAGE
        r2 = page * SHOP_ITEMS_PER_PAGE

        for i in range(r1, r2):
            item = SHOP_ITEMS[i]
            embed_shop.add_field(name = f"`{item['name']} ({item['price']} robux)`", value = item["description"], inline = False)

        await ctx.send(embed = embed_shop)

    @commands.command(
        name = "purchase-item",
        description = "Purchase item from shop",
        usage = "[amount (default = 1)] [item_name]"
    )
    async def purchase_item(self, ctx, amount: Optional[int] = 1, *, item_name):
        item = get_item_by_name(item_name)

        if item == None:
            embed_failure = discord.Embed(title = "Purchase Item", description = f"Invalid item name. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        price = (item["price"] * amount)
        user = get_user(ctx.author.id)

        if user[3] < price:
            embed_failure = discord.Embed(title = "Purchase Item", description = f"You don't have enough robux to purchase this item. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        inventory = json.loads(user[6])

        if amount > inventory.count(-1):
            embed_failure = discord.Embed(title = "Purchase Item", description = f"You don't have enough space in your inventory. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        self.remove_robux(ctx.author.id, price)

        add_item = True
        if "callback" in item:
            add_item = await item["callback"](ctx, inventory)

        if add_item:
            for i in range(amount):
                for j in range(len(inventory)):
                    if inventory[j] == -1:
                        inventory[j] = item["id"]
                        break

        cursor.execute("UPDATE users SET inventory = %s WHERE user_id = %s", (json.dumps(inventory), ctx.author.id,))
        db.commit()

        embed_success = discord.Embed(title = "Purchase Item", description = f"You bought {item['name']} (Amount: {amount}) for {price} robux. :white_check_mark:", colour = discord.Colour.green())
        embed_success.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        await ctx.send(embed = embed_success)

    @commands.command(
        name = "sell-item",
        description = "Sell item from your inventory",
        usage = "[amount (default = 1)] [item_name]"
    )
    async def sell_item(self, ctx, amount: Optional[int] = 1, *, item_name):
        item = get_item_by_name(item_name)

        if item == None:
            embed_failure = discord.Embed(title = "Sell Item", description = f"Invalid item name. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        inventory = json.loads(get_user(ctx.author.id)[6])

        if amount > inventory.count(item["id"]):
            embed_failure = discord.Embed(title = "Sell Item", description = f"You don't that amount of items. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        robux = (round(item["price"] / 2) * amount)

        for i in range(amount):
            for j in range(len(inventory)):
                if inventory[j] == item["id"]:
                    inventory[j] = -1
                    break

        self.give_robux(ctx.author.id, robux)

        cursor.execute("UPDATE users SET inventory = %s WHERE user_id = %s", (json.dumps(inventory), ctx.author.id,))
        db.commit()

        embed_success = discord.Embed(title = "Purchase Item", description = f"You sold {item['name']} (Amount: {amount}) for {robux} robux. :white_check_mark:", colour = discord.Colour.green())
        embed_success.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        await ctx.send(embed = embed_success)

    @commands.command(
        description = "Shows your inventory",
        usage = "[page (default = 1)]",
        aliases = ["inv"]
    )
    async def inventory(self, ctx, page: int = 1):
        global SHOP_ITEMS

        embed_inventory = discord.Embed(title = "Inventory", colour = discord.Colour.green())
        embed_inventory.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        inventory = json.loads(get_user(ctx.author.id)[6])
        inventory_count = []

        for item in SHOP_ITEMS:
            count = inventory.count(item["id"])

            if count != 0:
                inventory_count.append({"id": item["id"], "count": count})

        if len(inventory_count) == 0:
            embed_inventory.description = "Your inventory is empty :("
            return await ctx.send(embed = embed_inventory)

        pages = ceil(len(inventory_count) / INVENTORY_ITEMS_PER_PAGE)
        embed_inventory.set_footer(text = f"Page: {page} / {pages}")

        if page < 1 or page > pages:
            embed_failure = discord.Embed(title = "Inventory", description = "Invalid page. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        r1 = (page - 1) * INVENTORY_ITEMS_PER_PAGE
        r2 = page * INVENTORY_ITEMS_PER_PAGE

        for i in range(r1, r2):
            try:
                item = get_item_by_id(inventory_count[i]["id"])
                embed_inventory.add_field(name = f"`{item['name']}`", value = f"Amount: {inventory_count[i]['count']}", inline = False)
            except IndexError:
                break

        if len(embed_inventory.fields) == 0:
            embed_inventory.description = "Your inventory is empty :("

        await ctx.send(embed = embed_inventory)

    @commands.command(
        name = "give-item",
        description = "Give item to another user",
        usage = "[target] [amount (default = 1)] [item_name]"
    )
    async def give_item(self, ctx, target: discord.Member, amount: Optional[int] = 1, *, item_name):
        if target == ctx.author or target.bot:
            return

        if ctx.author.id in self.tradingUsers:
            embed_failure = discord.Embed(title = "Give Item", description = f"You currently sent trade to someone else. Wait when they accept trade or trade expires. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        item = get_item_by_name(item_name)

        if item == None:
            embed_failure = discord.Embed(title = "Give Item", description = f"Invalid item name. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        user_inventory = json.loads(get_user(ctx.author.id)[6])

        if amount > user_inventory.count(item["id"]):
            embed_failure = discord.Embed(title = "Give Item", description = f"You don't have that amount of items. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        target_inventory = json.loads(get_user(target.id)[6])

        if amount > target_inventory.count(-1):
            embed_failure = discord.Embed(title = "Give Item", description = f"You can't give this user that amount of items because they don't have enough space in inventory. :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

        self.tradingUsers.append(ctx.author.id)

        await ctx.send(f"{target.mention}, {ctx.author.mention} wants to give you {item_name} (Amount: {amount}). Would you like to accept? (y/n)\n(30 seconds to accept)")
        message = await self.bot.wait_for("message", timeout = 30.0, check = lambda message: message.author == target and message.channel == ctx.channel)
        answer = message.content.lower()

        if answer == "n":
            await ctx.send(f"{ctx.author.mention}, {target.mention} declined your gift. :x:")
            return self.tradingUsers.remove(ctx.author.id)
        elif answer != "y":
            return self.tradingUsers.remove(ctx.author.id)

        for i in range(amount):
            for j in range(len(user_inventory)):
                if user_inventory[j] == item["id"]:
                    user_inventory[j] = -1
                    for x in range(len(target_inventory)):
                        if target_inventory[x] == -1:
                            target_inventory[x] = item["id"]
                            break
                    break

        cursor.executemany("UPDATE users SET inventory = %s WHERE user_id = %s", [(json.dumps(user_inventory), ctx.author.id), (json.dumps(target_inventory), target.id)])
        db.commit()

        embed_success = discord.Embed(title = "Give Item", description = f"You gave {item['name']} (Amount: {amount}) to {target.mention}. :white_check_mark:", colour = discord.Colour.green())
        embed_success.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

        await ctx.send(embed = embed_success)
        self.tradingUsers.remove(ctx.author.id)

    @commands.command(
        name = "daily-reward",
        description = "Claim your daily reward."
    )
    async def daily_reward(self, ctx):
        user = get_user(ctx.author.id)
        tm = user[7]

        if tm == None:
            cursor.execute("UPDATE users SET daily_reward_time = %s WHERE user_id = %s", (time.time(), ctx.author.id,))
            tm = time.time()

        if time.time() >= tm:
            cursor.execute(
            f"""
            UPDATE users SET daily_reward_time = %s WHERE user_id = %s;
            UPDATE users SET robux = robux + {DAILY_REWARD} WHERE user_id = %s
            """, (time.time() + 86400, ctx.author.id, ctx.author.id,))

            embed_success = discord.Embed(title = "Daily Reward", description = f"You claimed your daily reward ({DAILY_REWARD} robux). :white_check_mark:", colour = discord.Colour.green())
            embed_success.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            await ctx.send(embed = embed_success)
        else:
            embed_failure = discord.Embed(title = "Daily reward", description = f"You can claim your daily reward after {time.strftime('%H', time.gmtime(user[7] - time.time()))} hour(s). :x:", colour = discord.Colour.red())
            embed_failure.set_author(name = ctx.author, icon_url = str(ctx.author.avatar_url))

            return await ctx.send(embed = embed_failure)

    @commands.command(
        name = "add-stat"
    )
    @commands.is_owner()
    async def add_stat(self, ctx, target: discord.Member, stat, value):
        cursor.execute(f"UPDATE users SET {stat} = {stat} + {value} WHERE user_id = %s", (target.id,))

    @commands.command(
        name = "set-stat"
    )
    @commands.is_owner()
    async def set_stat(self, ctx, target: discord.Member, stat, value):
        cursor.execute(f"UPDATE users SET {stat} = {value} WHERE user_id = %s", (target.id,))

    def cog_unload(self):
        asyncio.run(self.session.close())

    @commands.command(
        name = "global-wipe"
    )
    @commands.is_owner()
    async def global_wipe(self, ctx):
        cursor.execute("TRUNCATE users;")

        await self.bot.change_presence(
            activity = discord.Activity(name = "global wipe!", type = discord.ActivityType.watching),
            status = discord.Status.dnd
        )

def setup(bot):
    bot.add_cog(Economy(bot))