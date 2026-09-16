import pandas as pd
import numpy as np
import os
import mysql.connector
import re

# ============================================================
# File locations
# ============================================================

csv_folder = "/Users/alinahuan/Documents/VSCODE PROJECTS/Badminton Model V2/CSV Files"

# ============================================================
# Load match data
# ============================================================

matches_df = pd.read_csv(
    os.path.join(csv_folder, "data_df.csv")
)

# Remove extra index column if it exists
if "Unnamed: 0" in matches_df.columns:
    matches_df = matches_df.drop(columns=["Unnamed: 0"])


# ============================================================
# Load ranking data
# ============================================================

MS_rank = pd.read_csv(os.path.join(csv_folder, "MS_rank.csv"))
WS_rank = pd.read_csv(os.path.join(csv_folder, "WS_rank.csv"))
MD_rank = pd.read_csv(os.path.join(csv_folder, "MD_rank.csv"))
WD_rank = pd.read_csv(os.path.join(csv_folder, "WD_rank.csv"))
XD_rank = pd.read_csv(os.path.join(csv_folder, "XD_rank.csv"))


# ============================================================
# MATCH DATA FORMATTING
# ============================================================

matches_df["Number of Sets Played"] = pd.to_numeric(
    matches_df["Number of Sets Played"],
    errors="coerce"
).astype("Int64")

matches_df["Retired"] = pd.to_numeric(
    matches_df["Retired"],
    errors="coerce"
).astype("Int64")

matches_df["Team 1 Seed"] = pd.to_numeric(
    matches_df["Team 1 Seed"],
    errors="coerce"
)

matches_df["Team 2 Seed"] = pd.to_numeric(
    matches_df["Team 2 Seed"],
    errors="coerce"
)

matches_df["Match Duration (min)"] = pd.to_numeric(
    matches_df["Match Duration (min)"],
    errors="coerce"
)

# Score columns
score_columns = [
    "Points Set 1 Team 1",
    "Points Set 1 Team 2",
    "Points Set 2 Team 1",
    "Points Set 2 Team 2",
    "Points Set 3 Team 1",
    "Points Set 3 Team 2",
    "Total Points Team 1",
    "Total Points Team 2",
    "Sets Won Team 1",
    "Sets Won Team 2",
    "Total Game Points Team 1",
    "Total Game Points Team 2",
    "Most Consecutive Points Team 1",
    "Most Consecutive Points Team 2"
]

for col in score_columns:
    if col in matches_df.columns:
        matches_df[col] = pd.to_numeric(
            matches_df[col],
            errors="coerce"
        )


# Convert date
matches_df["Tournament Date"] = pd.to_datetime(
    matches_df["Tournament Date"],
    errors="coerce"
)
matches_df["Tournament Name"] = (
    matches_df["Tournament Name"]
    .str.replace("_", " ", regex=False)
    .str.replace(r"\b\d{4}\b", "", regex=True)
    .str.strip()
)

# ============================================================
# RECALCULATE MATCH WINNER
# ============================================================

def calculate_match_winner(row):

    team1_sets = row["Sets Won Team 1"]
    team2_sets = row["Sets Won Team 2"]

    # If either value is missing, cannot determine winner
    if pd.isna(team1_sets) or pd.isna(team2_sets):
        return None

    # Team 1 wins
    if team1_sets > team2_sets:
        return row["Team 1 Name(s)"]

    # Team 2 wins
    elif team2_sets > team1_sets:
        return row["Team 2 Name(s)"]

    # Same number of sets = draw
    else:
        return "Draw"


matches_df["Match Winner"] = matches_df.apply(
    calculate_match_winner,
    axis=1
)

# ============================================================
# CREATE MATCH ID
# ============================================================

# Give every match a unique ID
matches_df.insert(
    0,
    "Match ID",
    ["M" + str(i).zfill(5) for i in range(1, len(matches_df) + 1)]
)


# ============================================================
# RANKING DATA FORMATTING
# ============================================================

ranking_data = [
    (MS_rank, "MS"),
    (WS_rank, "WS"),
    (MD_rank, "MD"),
    (WD_rank, "WD"),
    (XD_rank, "XD")
]

ranking_list = []

for df, discipline in ranking_data:

    df = df.copy()

    df["Rank"] = pd.to_numeric(
        df["Rank"],
        errors="coerce"
    )

    df["Points Accumulated"] = pd.to_numeric(
        df["Points Accumulated"]
        .astype(str)
        .str.replace(",", ""),
        errors="coerce"
    )

    # Standardize names
    df["Name"] = (
        df["Name"]
        .astype(str)
        .str.strip()
        .str.title()
    )

    # Standardize country
    df["Country/Territory"] = (
        df["Country/Territory"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Convert date
    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    # Add discipline
    df["Discipline"] = discipline

    ranking_list.append(df)


# ============================================================
# COMBINE ALL FIVE RANKING TABLES
# ============================================================

rankings_df = pd.concat(
    ranking_list,
    ignore_index=True
)

rankings_df["Ranking ID"] = [
    f"R{i:05d}"
    for i in range(1, len(rankings_df) + 1)
]


rankings_df = rankings_df[
    [
        "Ranking ID",
        "Rank",
        "Country/Territory",
        "Name",
        "Date",
        "Points Accumulated",
        "Discipline"
    ]
]


# ============================================================
# STANDARDIZE PLAYER NAMES
# ============================================================

def clean_player_name(name):

    if pd.isna(name):
        return None

    name = str(name).strip()

    # Normalize whitespace
    name = re.sub(r"\s+", " ", name)

    # Standardize capitalization
    name = name.title()

    return name


# Apply to ranking names
rankings_df["Name"] = rankings_df["Name"].apply(
    clean_player_name
)


# ============================================================
# SPLIT TEAM NAMES INTO INDIVIDUAL PLAYERS
# ============================================================

def split_team(team):

    if pd.isna(team):
        return []

    team = str(team).strip()

    if not team:
        return []

    # Doubles teams can appear in different formats:
    #
    # "Player A, Player B"
    # "Player A / Player B"
    # "Player A & Player B"

    if "," in team:
        players = team.split(",")

    elif "/" in team:
        players = team.split("/")

    elif " & " in team:
        players = team.split(" & ")

    else:
        players = [team]

    return [
        clean_player_name(player)
        for player in players
        if clean_player_name(player)
    ]


def clean_nationality(nationality):

    if pd.isna(nationality):
        return None

    nationality = str(nationality).strip().upper()

    country_code_map = {
    "ALGERIA": "ALG",
    "AUSTRALIA": "AUS",
    "BELGIUM": "BEL",
    "BRAZIL": "BRA",
    "BULGARIA": "BUL",
    "CANADA": "CAN",
    "CHINA": "CHN",
    "CHINESETAIPEI": "TPE",
    "CZECHREPUBLIC": "CZE",
    "DENMARK": "DEN",
    "EGYPT": "EGY",
    "ENGLAND": "ENG",
    "ESTONIA": "EST",
    "FINLAND": "FIN",
    "FRANCE": "FRA",
    "GERMANY": "GER",
    "HONGKONG": "HKG",
    "INDIA": "IND",
    "INDONESIA": "INA",
    "IRELAND": "IRL",
    "ISRAEL": "ISR",
    "JAPAN": "JPN",
    "KOREA": "KOR",
    "MALAYSIA": "MAS",
    "MYANMAR": "MYA",
    "NETHERLANDS": "NED",
    "NEWZEALAND": "NZL",
    "NIGERIA": "NGR",
    "NORWAY": "NOR",
    "POLAND": "POL",
    "RUSSIA": "RUS",
    "SCOTLAND": "SCO",
    "SINGAPORE": "SGP",
    "SLOVAKIA": "SVK",
    "SPAIN": "ESP",
    "SWEDEN": "SWE",
    "SWITZERLAND": "SUI",
    "THAILAND": "THA",
    "TURKEY": "TUR",
    "UKRAINE": "UKR",
    "UNITEDSTATES": "USA",
    "VIETNAM": "VIE",
    "WALES": "WAL"
}

    return country_code_map.get(
        nationality,
        nationality
    )

# ============================================================
# CREATE PLAYER LIST FROM MATCH DATA
# ============================================================

match_players_list = []

for _, row in matches_df.iterrows():

    team1_players = split_team(
        row["Team 1 Name(s)"]
    )

    team2_players = split_team(
        row["Team 2 Name(s)"]
    )

    for player in team1_players:
        match_players_list.append({
            "Match ID": row["Match ID"],
            "Player Name": player,
            "Team": "Team 1"
        })

    for player in team2_players:
        match_players_list.append({
            "Match ID": row["Match ID"],
            "Player Name": player,
            "Team": "Team 2"
        })


match_players_df = pd.DataFrame(match_players_list)


# ============================================================
# CREATE PLAYERS TABLE
# ============================================================

# Clean ranking player names before matching
rankings_df["Name"] = rankings_df["Name"].apply(clean_player_name)

# Players appearing in matches
match_player_names = set(
    match_players_df["Player Name"].dropna()
)

# Players appearing in rankings
ranking_player_names = set(
    rankings_df["Name"].dropna()
)

# Combine both sources
all_player_names = (
    match_player_names |
    ranking_player_names
)

players_df = pd.DataFrame({
    "Player Name": sorted(all_player_names)
})



# ============================================================
# ADD PLAYER ID
# ============================================================

players_df.insert(
    0,
    "Player ID",
    [
        "P" + str(i).zfill(5)
        for i in range(1, len(players_df) + 1)
    ]
)



# ============================================================
# ADD NATIONALITY TO PLAYERS
# ============================================================

player_country_list = []

for _, row in matches_df.iterrows():

    # --------------------------------------------------------
    # Team 1
    # --------------------------------------------------------

    team1_players = split_team(
        row["Team 1 Name(s)"]
    )

    team1_country = clean_nationality(
        row["Team 1 Nationalities"]
    )

    # Every player on Team 1 gets Team 1's nationality
    for player in team1_players:

        player_country_list.append({
            "Player Name": player,
            "Nationality": team1_country
        })

    # --------------------------------------------------------
    # Team 2
    # --------------------------------------------------------

    team2_players = split_team(
        row["Team 2 Name(s)"]
    )

    team2_country = clean_nationality(
        row["Team 2 Nationalities"]
    )

    # Every player on Team 2 gets Team 2's nationality
    for player in team2_players:

        player_country_list.append({
            "Player Name": player,
            "Nationality": team2_country
        })


# Convert to DataFrame
match_player_country = pd.DataFrame(
    player_country_list
)


# ------------------------------------------------------------
# Get most common nationality for each player
# ------------------------------------------------------------

if not match_player_country.empty:

    match_player_country = (
        match_player_country
        .groupby("Player Name")["Nationality"]
        .agg(
            lambda x: x.mode().iloc[0]
            if not x.mode().empty
            else None
        )
        .reset_index()
    )


# ------------------------------------------------------------
# Get nationality from ranking data as backup
# ------------------------------------------------------------

ranking_player_country = (
    rankings_df
    .dropna(subset=["Name"])
    .groupby("Name")["Country/Territory"]
    .agg(
        lambda x: x.mode().iloc[0]
        if not x.mode().empty
        else None
    )
    .reset_index()
)

ranking_player_country.columns = [
    "Player Name",
    "Nationality"
]


# ------------------------------------------------------------
# Combine nationality sources
# ------------------------------------------------------------

players_df = players_df.merge(
    match_player_country,
    on="Player Name",
    how="left"
)

players_df = players_df.rename(
    columns={
        "Nationality": "Match Nationality"
    }
)

players_df = players_df.merge(
    ranking_player_country,
    on="Player Name",
    how="left"
)

players_df = players_df.rename(
    columns={
        "Nationality": "Ranking Nationality"
    }
)


# ------------------------------------------------------------
# Use match nationality first,
# ranking nationality as backup
# ------------------------------------------------------------

players_df["Nationality"] = (
    players_df["Match Nationality"]
    .fillna(players_df["Ranking Nationality"])
)


# Remove temporary columns
players_df = players_df.drop(
    columns=[
        "Match Nationality",
        "Ranking Nationality"
    ]
)

# ============================================================
# CREATE PLAYER ID LOOKUP
# ============================================================

player_id_lookup = dict(
    zip(
        players_df["Player Name"],
        players_df["Player ID"]
    )
)


# ============================================================
# ADD PLAYER ID TO MATCH_PLAYERS
# ============================================================

match_players_df["Player ID"] = (
    match_players_df["Player Name"]
    .map(player_id_lookup)
)

# ============================================================
# ADD PLAYER ID TO RANKINGS
# ============================================================

rankings_df["Player ID"] = (
    rankings_df["Name"]
    .map(player_id_lookup)
)

# ============================================================
# ADD MATCH DATE + DISCIPLINE TO MATCH_PLAYERS
# ============================================================

match_info = matches_df[
    [
        "Match ID",
        "Tournament Date",
        "Discipline"
    ]
].copy()

match_players_df = match_players_df.merge(
    match_info,
    on="Match ID",
    how="left"
)

# ============================================================
# ADD MATCH RESULT TO MATCH_PLAYERS
# ============================================================
def get_result(row):

    match = matches_df[
        matches_df["Match ID"] == row["Match ID"]
    ]

    if match.empty:
        return None

    match = match.iloc[0]

    team1_sets = match["Sets Won Team 1"]
    team2_sets = match["Sets Won Team 2"]

    # Cannot determine result if set information is missing
    if pd.isna(team1_sets) or pd.isna(team2_sets):
        return None

    # Draw
    if team1_sets == team2_sets:
        return "Draw"

    # Player is on Team 1
    if row["Team"] == "Team 1":
        if team1_sets > team2_sets:
            return "Win"
        else:
            return "Loss"

    # Player is on Team 2
    elif row["Team"] == "Team 2":
        if team2_sets > team1_sets:
            return "Win"
        else:
            return "Loss"

    return None

match_players_df["Result"] = match_players_df.apply(
    get_result,
    axis=1
)


# ============================================================
# FIND PLAYER RANKING AT TIME OF MATCH
# ============================================================

# Make sure dates are datetime
match_players_df["Tournament Date"] = pd.to_datetime(
    match_players_df["Tournament Date"],
    errors="coerce"
)

rankings_for_match = rankings_df[
    [
        "Player ID",
        "Date",
        "Discipline",
        "Rank"
    ]
].copy()

rankings_for_match["Date"] = pd.to_datetime(
    rankings_for_match["Date"],
    errors="coerce"
)

# Remove rankings where we cannot identify the player/date/rank
rankings_for_match = rankings_for_match.dropna(
    subset=[
        "Player ID",
        "Date",
        "Rank"
    ]
)

# Sort by the actual date being matched
rankings_for_match = rankings_for_match.sort_values(
    ["Date", "Player ID", "Discipline"]
).reset_index(drop=True)

match_players_df = match_players_df.sort_values(
    ["Tournament Date", "Player ID", "Discipline"]
).reset_index(drop=True)


# Find the most recent ranking on or before the match date
match_players_df = pd.merge_asof(
    match_players_df,
    rankings_for_match,
    left_on="Tournament Date",
    right_on="Date",
    by=["Player ID", "Discipline"],
    direction="backward"
)

# Rename ranking date
match_players_df = match_players_df.rename(
    columns={
        "Date": "Ranking Date"
    }
)

# ============================================================
# CREATE TEAM COMPOSITIONS
# ============================================================

team_players = (
    match_players_df
    .groupby(["Match ID", "Team"])["Player Name"]
    .agg(lambda x: " | ".join(sorted(x)))
    .reset_index()
)

# Rename team composition
team_players = team_players.rename(
    columns={"Player Name": "Team Players"}
)

# Add team composition back to match_players_df
match_players_df = match_players_df.merge(
    team_players,
    on=["Match ID", "Team"],
    how="left"
)

# ============================================================
# CALCULATE TEAM RANKS + WINNER/LOSER RANK + RANK GAP
# ============================================================

# Average ranking for each team in each match
# Average ranking for each team in each match, always rounded down
team_average_ranks = (
    match_players_df
    .groupby(["Match ID", "Team"])["Rank"]
    .mean()
    .apply(np.floor)
    .unstack()
    .rename(columns={
        "Team 1": "Team 1 Average Rank",
        "Team 2": "Team 2 Average Rank"
    })
    .reset_index()
)


# Add team rankings to match_players
match_players_df = match_players_df.merge(
    team_average_ranks,
    on="Match ID",
    how="left"
)


# Get winning team
winning_team = (
    match_players_df[
        match_players_df["Result"] == "Win"
    ]
    .groupby("Match ID")["Team"]
    .first()
    .rename("Winning Team")
    .reset_index()
)

match_players_df = match_players_df.merge(
    winning_team,
    on="Match ID",
    how="left"
)


# Winner rank
match_players_df["Winner Rank"] = (
    match_players_df["Team 1 Average Rank"]
    .where(
        match_players_df["Winning Team"] == "Team 1",
        match_players_df["Team 2 Average Rank"]
    )
)


# Loser rank
match_players_df["Loser Rank"] = (
    match_players_df["Team 2 Average Rank"]
    .where(
        match_players_df["Winning Team"] == "Team 1",
        match_players_df["Team 1 Average Rank"]
    )
)


# Positive = winner had a worse ranking than loser
match_players_df["Rank Gap"] = (
    match_players_df["Winner Rank"]
    - match_players_df["Loser Rank"]
)

# ============================================================
# CLEAN UP TABLE COLUMNS
# ============================================================

# Players
players_df = players_df[
    [
        "Player ID",
        "Player Name",
        "Nationality"
    ]
]


# Match Players
match_players_df = match_players_df[
    [
        "Match ID",
        "Player ID",
        "Player Name",
        "Team",
        "Team Players",
        "Result",
        "Tournament Date",
        "Discipline",
        "Rank",
        "Ranking Date",
        "Winner Rank",
        "Loser Rank",
        "Rank Gap"
    ]
]

# Rankings
rankings_df = rankings_df[
    [
        "Ranking ID",
        "Player ID",
        "Name",
        "Country/Territory",
        "Date",
        "Discipline",
        "Rank",
        "Points Accumulated"
    ]
]



# ============================================================
# CONNECT TO MYSQL DATABASE
# ============================================================

conn = mysql.connector.connect(
    host="localhost",
    port=3306,
    user="root",
    password="123",
    database="badmintondb"
)

cursor = conn.cursor()

print("Connected to MySQL database.")


# ============================================================
# CREATE SQL TABLES
# ============================================================

# Drop old tables first
# Order matters because of relationships

cursor.execute("DROP TABLE IF EXISTS match_players")
cursor.execute("DROP TABLE IF EXISTS rankings")
cursor.execute("DROP TABLE IF EXISTS players")
cursor.execute("DROP TABLE IF EXISTS matches")


# ------------------------------------------------------------
# MATCHES
# ------------------------------------------------------------

cursor.execute("""
CREATE TABLE matches (
    `Match ID` VARCHAR(20) PRIMARY KEY,
    `Tournament Name` VARCHAR(255),
    `Tournament Date` DATE,
    `Tournament Country` VARCHAR(100),
    `Discipline` VARCHAR(10),
    `Number of Sets Played` INT,
    `Retired` INT,
    `Match Duration (min)` FLOAT,
    `Team 1 Nationalities` TEXT,
    `Team 2 Nationalities` TEXT,
    `Team 1 Name(s)` TEXT,
    `Team 1 Seed` FLOAT,
    `Team 2 Name(s)` TEXT,
    `Team 2 Seed` FLOAT,
    `Points Set 1 Team 1` INT,
    `Points Set 1 Team 2` INT,
    `Points Set 2 Team 1` INT,
    `Points Set 2 Team 2` INT,
    `Points Set 3 Team 1` INT,
    `Points Set 3 Team 2` INT,
    `Total Points Team 1` INT,
    `Total Points Team 2` INT,
    `Sets Won Team 1` INT,
    `Sets Won Team 2` INT,
    `Total Game Points Team 1` INT,
    `Total Game Points Team 2` INT,
    `Most Consecutive Points Team 1` INT,
    `Most Consecutive Points Team 2` INT,
    `Team 1 Head to Head Analysis` TEXT,
    `Team 2 Head to Head Analysis` TEXT,
    `Match Winner` TEXT
)
""")


# ------------------------------------------------------------
# PLAYERS
# ------------------------------------------------------------

cursor.execute("""
CREATE TABLE players (
    `Player ID` VARCHAR(20) PRIMARY KEY,
    `Player Name` VARCHAR(255),
    `Nationality` VARCHAR(10)
)
""")


# ------------------------------------------------------------
# RANKINGS
# ------------------------------------------------------------

cursor.execute("""
    CREATE TABLE rankings (
        `Ranking ID` VARCHAR(20) PRIMARY KEY,
        `Player ID` VARCHAR(20),
        `Name` VARCHAR(255),
        `Country/Territory` VARCHAR(10),
        `Date` DATE,
        `Discipline` VARCHAR(10),
        `Rank` INT,
        `Points Accumulated` INT,

        FOREIGN KEY (`Player ID`)
            REFERENCES players(`Player ID`)
    )
""")


# ------------------------------------------------------------
# MATCH PLAYERS
# ------------------------------------------------------------
cursor.execute("""
    CREATE TABLE match_players (
        `Match ID` VARCHAR(20),
        `Player ID` VARCHAR(20),
        `Player Name` VARCHAR(255),
        `Team` VARCHAR(10),
        `Team Players` VARCHAR(255),
        `Result` VARCHAR(10),
        `Tournament Date` DATE,
        `Discipline` VARCHAR(10),
        `Rank` INT,
        `Ranking Date` DATE,
        `Winner Rank` FLOAT,
        `Loser Rank` FLOAT,
        `Rank Gap` FLOAT,

        PRIMARY KEY (`Match ID`, `Player ID`),

        FOREIGN KEY (`Match ID`)
            REFERENCES matches(`Match ID`),

        FOREIGN KEY (`Player ID`)
            REFERENCES players(`Player ID`)
    )
""")


# ============================================================
# INSERT MATCH DATA
# ============================================================

match_columns = list(matches_df.columns)

placeholders = ", ".join(
    ["%s"] * len(match_columns)
)

column_names = ", ".join(
    [f"`{col}`" for col in match_columns]
)

match_insert_query = f"""
INSERT INTO matches ({column_names})
VALUES ({placeholders})
"""

match_values = []

for _, row in matches_df.iterrows():

    values = []

    for col in match_columns:

        value = row[col]

        if pd.isna(value):
            value = None

        elif isinstance(value, pd.Timestamp):
            value = value.date()

        values.append(value)

    match_values.append(tuple(values))


cursor.executemany(
    match_insert_query,
    match_values
)

print(
    f"Uploaded {len(match_values)} matches."
)


# ============================================================
# INSERT PLAYERS
# ============================================================


player_columns = list(players_df.columns)

placeholders = ", ".join(
    ["%s"] * len(player_columns)
)

column_names = ", ".join(
    [f"`{col}`" for col in player_columns]
)

player_insert_query = f"""
INSERT INTO players ({column_names})
VALUES ({placeholders})
"""

player_values = []

for _, row in players_df.iterrows():

    values = []

    for col in player_columns:

        value = row[col]

        if pd.isna(value):
            value = None

        values.append(value)

    player_values.append(tuple(values))


cursor.executemany(
    player_insert_query,
    player_values
)

print(
    f"Uploaded {len(player_values)} players."
)


# ============================================================
# INSERT RANKING DATA
# ============================================================

ranking_columns = list(rankings_df.columns)

placeholders = ", ".join(
    ["%s"] * len(ranking_columns)
)

column_names = ", ".join(
    [f"`{col}`" for col in ranking_columns]
)

ranking_insert_query = f"""
INSERT INTO rankings ({column_names})
VALUES ({placeholders})
"""

ranking_values = []

for _, row in rankings_df.iterrows():

    values = []

    for col in ranking_columns:

        value = row[col]

        if pd.isna(value):
            value = None

        elif isinstance(value, pd.Timestamp):
            value = value.date()

        values.append(value)

    ranking_values.append(tuple(values))


cursor.executemany(
    ranking_insert_query,
    ranking_values
)

print(
    f"Uploaded {len(ranking_values)} ranking records."
)


# ============================================================
# INSERT MATCH_PLAYERS DATA
# ============================================================

match_player_columns = list(
    match_players_df.columns
)

placeholders = ", ".join(
    ["%s"] * len(match_player_columns)
)

column_names = ", ".join(
    [f"`{col}`" for col in match_player_columns]
)

match_player_insert_query = f"""
INSERT INTO match_players ({column_names})
VALUES ({placeholders})
"""

match_player_values = []

for _, row in match_players_df.iterrows():

    values = []

    for col in match_player_columns:

        value = row[col]

        if pd.isna(value):
            value = None

        values.append(value)

    match_player_values.append(tuple(values))


cursor.executemany(
    match_player_insert_query,
    match_player_values
)

print(
    f"Uploaded {len(match_player_values)} match-player records."
)


# ============================================================
# COMMIT CHANGES
# ============================================================

conn.commit()


# ============================================================
# CHECK TABLES
# ============================================================

cursor.execute("SHOW TABLES")

tables = cursor.fetchall()

print("\nTables in database:")

for table in tables:
    print("-", table[0])


# ============================================================
# CHECK ROW COUNTS
# ============================================================

print("\nRow counts:")

for table_name in [
    "matches",
    "players",
    "rankings",
    "match_players"
]:

    cursor.execute(
        f"SELECT COUNT(*) FROM `{table_name}`"
    )

    count = cursor.fetchone()[0]

    print(f"{table_name}: {count}")


# ============================================================
# CLOSE DATABASE
# ============================================================

cursor.close()
conn.close()

print("\nDatabase upload complete!")