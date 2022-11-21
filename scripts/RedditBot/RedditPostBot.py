# Standard Python libraries
import os
import praw
import sys

# My libaries
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Config

r = praw.Reddit(client_id=Config.config["reddit_client_id"], client_secret=Config.config["reddit_secret"], username=Config.config["reddit_username"], password=Config.config["reddit_password"], user_agent="/r/oldtimehockey stats bot by /u/SPRX97 v1.0")
r.validate_on_submit=True

f = open(Config.config["srcroot"] + "scripts/WeekVars.txt", "r")
year = int(f.readline().strip())
week = int(f.readline().strip())
f.close()

# PF Leaderboard
pf = open(Config.config["srcroot"] + "scripts/RedditBot/PFs/" + str(year) + "_Week_" + str(week) + ".txt", "r")
r.subreddit("OldTimeHockey").submit(str(year) + " Week " + str(week) + " PF Rankings", selftext=pf.read())

# Stats and Analysis Post
weekly = open(Config.config["srcroot"] + "scripts/RedditBot/weeks/" + str(year) + "_Week_" + str(week) + ".txt", "r")
r.subreddit("OldTimeHockey").submit(str(year) + " Week " + str(week) + " Stats and Analysis", selftext=weekly.read())

# Woppa Cup Tournament (needs to be updated each year)
r.subreddit("OldTimeHockey").submit("Woppa Cup " + str(year) + " Update", "https://challonge.com/woppacup23x")
