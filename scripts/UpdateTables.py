import requests
from lxml import html # xml parsing
import pymysql # sql queries
import sys
import Config
import re

from Shared import *

years_to_update = [] # can manually seed if necessary
playoffs_to_update = []

if len(sys.argv) == 1: # no arguments
    f = open(Config.config["srcroot"] + "scripts/WeekVars.txt", "r")
    year = int(f.readline().strip())
    week = int(f.readline().strip())

    years_to_update.append(year)
    if is_playoff_week(week, year):
        playoffs_to_update.append(year)
    f.close()
else:
    for arg in sys.argv[1:]:
        if len(arg) == 4:
            years_to_update.append(int(arg))
        elif len(arg) == 5 and arg[-1] == "p":
            playoffs_to_update.append(int(arg[:-1]))
        else:
            print("Invalid argument")
            quit()

def printHtml(root, depth):
    for n in range(0, depth):
        print(" ", end='')
    print(depth, end='')
    print(root.tag, root.get("class"), root.text)
    for child in root:
        printHtml(child, depth+1)

# More error-safe parseInt and parseFloat methods
def intP(str):
    if str == "":
        return 0
    return int(str)

def floatP(str):
    if str == "":
        return 0.0
    return float(str)

# Checks the standings pages of the given league and updates the datafile
def getStandings(leagueID, year):
    standingsURL = "http://www.fleaflicker.com/nhl/leagues/" + str(leagueID) + "?season=" + str(year)
    response = requests.get(standingsURL)
    root = html.document_fromstring(response.text)
    rows = root.cssselect(".table-striped")[0].findall("tr")
    champs = []
    for n in range(0, len(rows)):
        isChamp = len(rows[n].cssselect(".fa-trophy")) > 0

        if isChamp:
            teamID = rows[n].cssselect(".league-name")[0].findall("a")[0].get("href")
            if "?season" in teamID:
                teamID = teamID[(teamID.find("/teams/") + 7):teamID.find("?season")]
            else:
                teamID = teamID[(teamID.find("/teams/") + 7):]

            champs.append(teamID)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                                                             #
    #  Need some sort of error handling for if the HTML changes.  #
    #                                                             #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    leadersTabURL = "http://www.fleaflicker.com/nhl/leagues/" + str(leagueID) + "/leaders?season=" + str(year)
    response2 = requests.get(leadersTabURL)
    root2 = html.document_fromstring(response2.text)
    rows2 = root2.cssselect(".table-group")[0].findall("tr")
    coachRating = {}
    optimumPF = {}
    numrows = len(rows2)-1
    if numrows % 2 != 0:
        numrows += 1
    for n in range(0, numrows):
        teamID = rows2[n].cssselect(".league-name")[0].findall("a")[0].get("href")
        if "?season" in teamID:
            teamID = teamID[(teamID.find("/teams/") + 7):teamID.find("?season")]
        else:
            teamID = teamID[(teamID.find("/teams/") + 7):]

        try:
            val = rows2[n][10].text_content().replace(",","")

            optimumPF[teamID] = floatP(val.split("(")[0])
            coachRating[teamID] = floatP(val.split("(")[1][:-2])
        except:
            print("Trouble Finding Coach Rating")
            coachRating[teamID] = 0.0
            optimumPF[teamID] = 0.0

    all_teams = []

    standings = make_api_call(f"http://www.fleaflicker.com/api/FetchLeagueStandings?sport=NHL&league_id={leagueID}&season={year}")
    for team in standings["divisions"][0]["teams"]:
        team_id = str(team["id"])
        team_name = team["name"]

        user_id = 0
        if "owners" in team:
            user_id = str(team["owners"][0]["id"])
            user_name = team["owners"][0]["displayName"]
            if user_id == "591742":
                user_id = "157129" # override for rellek multiple accounts
            elif user_id == "698576":
                user_id = "1357398" # override for MWHazard multiple accounts

        # wins, losses, gamesBack, streak, pointsFor, pointsAgainst, coachRating*, isChamp, ties
        record = team["recordOverall"]
        wins = record["wins"] if "wins" in record else 0
        losses = record["losses"] if "losses" in record else 0
        ties = record["ties"] if "ties" in record else 0
        # gamesBack? -- don't really need this IIRC
        streak = team["streak"]["value"] if "value" in team["streak"] else 0
        points_for = team["pointsFor"]["value"]
        points_against = team["pointsAgainst"]["value"]

        # I don't think these values are necessary anymore,
        # but I'll have to disentangle some things to fully remove them
        # If GamesBack is necessary that can easily be calculated in SQL
        division = None
        games_back = 0

        # CR is stored above, but I should have enough info to figure it out
        # Should have enough info to get CR from, and isChamp I think I can figure out.
            # https://www.fleaflicker.com/api/FetchLeagueScoreboard?sport=NHL&league_id=12086&season=2020
            # https://www.fleaflicker.com/api/FetchLeagueBoxscore?sport=NHL&league_id=12086&fantasy_game_id=2579652&scoring_period=104
            # https://www.fleaflicker.com/api/FetchLeagueBoxscore?sport=NHL&league_id=12086&fantasy_game_id=2579653&scoring_period=108

        all_teams.append([team_id, team_name, user_id, user_name, division, wins, losses, games_back, streak, points_for, points_against, coachRating[team_id], team_id in champs, ties])

    return all_teams

def getPlayoffs(leagueID, year):
    playoffsURL = "http://www.fleaflicker.com/nhl/leagues/" + str(leagueID) + "/playoffs?season=" + str(year)
    response = requests.get(playoffsURL)
    root = html.document_fromstring(response.text)
    bracket = root.cssselect(".playoff-bracket")[0]

    teams = {}
    brackets = bracket.cssselect(".league-name")
    for n in range(0, len(brackets)):
        team = brackets[n]
        teamID = team.findall("a")[0].get("href")
        if "?season" in teamID:
            teamID = teamID[(teamID.find("/teams/") + 7):teamID.find("?season")]
        else:
            teamID = teamID[(teamID.find("/teams/") + 7):]
        points = team.getnext()

        if points != None:
            if teamID in teams:
                teams[teamID][2] += floatP(points.text_content())
            else:
                teams[teamID] = [0, 0, floatP(points.text_content()), 0.0, 0]
            teams[teamID][0] += len(points.cssselect(".scoreboard-win"))
            teams[teamID][1] += 1-len(points.cssselect(".scoreboard-win"))

        # points against... kinda hacky
        if n == 0:
            teams[teamID][3] += floatP(brackets[3].getnext().text_content())
            teams[teamID][4] = 1
        if n == 1:
            teams[teamID][3] += floatP(brackets[9].getnext().text_content())
        if n == 2:
            teams[teamID][3] += floatP(brackets[4].getnext().text_content())
            teams[teamID][4] = 4
        if n == 3:
            teams[teamID][3] += floatP(brackets[0].getnext().text_content())
        if n == 4:
            teams[teamID][3] += floatP(brackets[2].getnext().text_content())
            teams[teamID][4] = 5
        if n == 6:
            teams[teamID][3] += floatP(brackets[8].getnext().text_content())
            teams[teamID][4] = 3
        if n == 7:
            teams[teamID][3] += floatP(brackets[10].getnext().text_content())
        if n == 8:
            teams[teamID][3] += floatP(brackets[6].getnext().text_content())
            teams[teamID][4] = 6
        if n == 9:
            teams[teamID][3] += floatP(brackets[1].getnext().text_content())
        if n == 10:
            teams[teamID][3] += floatP(brackets[7].getnext().text_content())
            teams[teamID][4] = 2

    return teams

def demojify(text):
    regex_pattern = re.compile(pattern="["
        u"\U0001F600-\U0001F64F" # emoticons
        u"\U0001F300-\U0001F5FF" # symbols & pictographs
        u"\U0001F680-\U0001F6FF" # transport & map symbols
        u"\U0001F1E0-\U0001F1FF" # flags (iOS)
        "]+", flags = re.UNICODE)
    return regex_pattern.sub(r'', text)

if __name__ == "__main__":
    db = pymysql.connect(host=Config.config["sql_hostname"], user=Config.config["sql_username"], passwd=Config.config["sql_password"], db=Config.config["sql_dbname"])
    cursor = db.cursor()

    for year in years_to_update:
        cursor.execute("SELECT * from Leagues where year=" + str(year)) # queries for all leagues that year
        leagues = cursor.fetchall()
        for league in leagues:
            teams = getStandings(league[0], league[1])
            for next in teams:
                next[1] = next[1].replace(";", "") # prevent sql injection
                next[1] = next[1].replace("'", "''") # correct quote escaping
                next[1] = next[1].replace(u"\u2019", "''") # another type of quote?
                next[1] = demojify(next[1])
                next[3] = next[3].replace(";", "") # prevent sql injection
                next[3] = next[3].replace("'", "''") # correct quote escaping
                try:
                    if next[3][-2] == "+":
                        next[3] = next[3][:-3] # elimites "+1" for managers with co-managers
                except:
                    pass

                if str(next[2]) == "591742":
                    next[2] = 157129 # override for rellek multi accounts...
                elif str(next[2]) == "698576":
                    next[2] = 1357398 # override for MWHazard's old account

                cursor.execute("SELECT * from Teams where teamID = " + next[0] + " AND year=" + str(year))
                data = cursor.fetchall()
                if len(data) == 0: # insert new team into table (should only happen once)
                    # print(next[1])
                    cursor.execute("INSERT into Teams values (" + str(next[0]) + ", " + str(league[0]) + ", " + str(next[2]) + ", '" + \
                    next[1] + "', " + str(next[5]) + ", " + str(next[6]) + ", " + str(next[7]) + ", " + str(next[8]) + ", " + \
                    str(next[9]) + ", " + str(next[10]) + ", 0, " + str(next[11]) + ", " + str(next[12]) +  ", 0.0, 0.0, -1, -1," + str(next[2]) + ", " + str(year) + ", " + str(next[13]))

                elif len(data) == 1:
                    if intP(data[0][2]) != intP(next[2]) and intP(next[2]) != 0:
                        cursor.execute("UPDATE Teams set ownerID=" + str(next[2]) + ", replacement=1 where teamID=" + str(next[0]) + " AND year=" + str(year))

                    cursor.execute("UPDATE Teams set  name='" + next[1] + \
                    "', wins=" + str(next[5]) + ", losses=" + str(next[6]) + ", ties=" + str(next[13]) + ", gamesBack=" + str(next[7]) + \
                    ", streak=" + str(next[8]) + ", pointsFor=" + str(next[9]) + ", pointsAgainst=" + str(next[10]) + \
                    ", coachRating=" + str(next[11]) + ", isChamp=" + str(next[12]) +  " where teamID=" + str(next[0]) + " AND year=" + str(year))
                else:
                    raise Exception("Error: more than one team matches teamID: " + str(next[0]))

                # only update the user if there is actually another user
                if (next[2] != 0):
                    cursor.execute("SELECT * from Users where FFid = " + str(next[2]))
                    data = cursor.fetchall()
                    if len(data) == 0: # insert new user into table (should only happen once)
                        cursor.execute("INSERT into Users values (" + str(next[2]) + ", '" + next[3] + \
                                        "', NULL)")
                    elif len(data) == 1:
                        cursor.execute("UPDATE Users set FFname='" + next[3] \
                        + "' where FFid=" + str(next[2]))
                    else:
                        raise Exception("Error: more than one user matches userID: " + str(next[2]))

    for year in playoffs_to_update:
        cursor.execute("SELECT * from Leagues where year=" + str(year)) # queries for all leagues that year
        leagues = cursor.fetchall()
        for league in leagues:
            teams_post = getPlayoffs(league[0], league[1])
            for next in teams_post:
                cursor.execute("SELECT * from Teams_post where teamID = " + next + " AND year=" + str(year))
                data = cursor.fetchall()
                if len(data) == 0: # new team
                    cursor.execute("INSERT into Teams_post values (" + next + ", " + str(teams_post[next][0]) + ", " + str(teams_post[next][1]) + \
                    ", " + str(teams_post[next][2]) + ", " + str(teams_post[next][3]) + ", " + str(teams_post[next][4]) + ", " + str(year) +  ")")
                elif len(data) == 1:
                    cursor.execute("UPDATE Teams_post set wins=" + str(teams_post[next][0]) + ", losses=" + str(teams_post[next][1]) + \
                    ", pointsFor=" + str(teams_post[next][2]) + ", pointsAgainst=" + str(teams_post[next][3]) + ", seed=" + str(teams_post[next][4]) + " where teamID=" + next + " AND year=" + str(year))
                else:
                    raise Exception("Error: more than one team matches teamID: " + next)

    db.commit()
