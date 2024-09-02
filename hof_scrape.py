from curses.ascii import isupper
from lib2to3.pgen2 import token
import requests
import datetime
import pytz
import time
import json
import argparse
from bs4 import BeautifulSoup
import extra_lists
from tqdm import tqdm
import pygsheets
import additional_funcs

class Game:
    def __init__(self, title, score, true_review_count, top_review_count, top_score, main_page_review_count, year, url):    
        self.title = title
        self.score = score
        self.true_review_count = true_review_count
        self.top_review_count = top_review_count
        self.top_score = top_score,
        self.main_page_review_count = main_page_review_count
        self.year = year
        self.url = url

def print_review_score_counts(reviews):
    reviews.sort(reverse=True)
    count = 1
    j = reviews[0]
    for i in range(1, len(reviews)):
        if reviews[i] != j:
            print(f"{j} * {count}")
            j = reviews[i]
            count = 1
        else:
            count += 1
    print(f"{j} * {count}")
    print(f"{sum(reviews)/len(reviews)} from {len(reviews)} reviews")

def insert_into_true_list(game, true_list, true_list_titles):
    if true_list == []:
        true_list.append(game)
        true_list_titles.append(game.title)
    elif game.title in true_list_titles:
        for true_game in true_list:
            if true_game.title == game.title:
                if game.score > true_game.score:
                    i = len(true_list) - 1
                    while game.score >= true_list[i].score:
                        if i == 0:
                            true_list.insert(0, game)
                            return
                        i -= 1
                        if i == 0:
                            break
                    true_game.score = game.score
                    true_list.remove(true_game)
                    true_list.insert(i + 1, true_game)
    else:
        i = len(true_list) - 1
        while game.score >= true_list[i].score:
            # Edge case where game must be swapped into first place (EX: top game of gen on website is wrong)
            if i == 0:
                true_list.insert(0, game)
                return
            i -= 1
            if i == 0:
                break
        true_list.insert(i + 1, game)
        true_list_titles.append(game.title)


parser = argparse.ArgumentParser()
parser.add_argument("-s", "--specific_game")
parser.add_argument("-n", "--game_number")
args = parser.parse_args()
if args.specific_game and args.game_number:
    additional_funcs.specific_game(args.specific_game, args.game_number)
    exit()

hof_list = []
runtime_datestring = f'As of {datetime.datetime.now(pytz.timezone("US/Eastern")).strftime("%B %d, %Y at %#I:%M %p")}'
start_time = time.time()

page_count = 20
num_of_games = 50

scrape_url = ""
print("Filtering games...")
for i in range(1, page_count):
    if i == 1:
        scrape_url = "https://opencritic.com/browse/all"
    elif i > 1:
        scrape_url = f"https://opencritic.com/browse/all?page={i}"

    r = requests.get(scrape_url)
    soup = BeautifulSoup(r.content, "html.parser")

    chunk = soup.select_one('.desktop-game-display div')
    rows = chunk.select('.row')
    for row in rows:
        title = row.select_one(".game-name").text.strip()
        if title in extra_lists.remove_list:
            continue
        hof_list.append(Game(
            title = title,
            score = row.select_one(".score").text.strip(),
            true_review_count = 0,
            top_review_count = 0,
            top_score = 0,
            main_page_review_count = 0,
            year = int(row.select_one(".first-release-date").select_one("span").text.strip()[-4:]),
            url = row.select_one("a")['href']
        ))

with open("opencritic_hall_of_fame.json", "r") as f:
    data = f.read()
if not data:
    data = "{}"
file_in_dict = json.loads(data)
file_out_dict = {}
x_list = []
winner_names = []
runner_up_dict = {}

client = pygsheets.authorize(service_account_file="opencritic-hall-of-fame-05b0a303f5b6.json")
sheet = client.open("opencritic_hall_of_fame")
true_list_gen8 = []
true_list_gen8_titles = []
true_list_gen9 = []
true_list_gen9_titles = []

any_changes = False
# for game_index in range(0, len(hof_list)):            # Un-comment to disable progress bar
for game_index in tqdm(range(0, len(hof_list)), desc="Aggregating reviews from opencritic.com and assembling Hall of Fame list..."):
    game = hof_list[game_index]
    score_sum = 0
    score_count = 0
    top_score_sum = 0
    top_score_count = 0
    current_page = 0
    last_page = False

    # Get total number of reviews from game's main page (used later for error-checking)
    error_check_req = requests.get(f"https://opencritic.com/{game.url}/")
    soup = BeautifulSoup(error_check_req.content, "html.parser")
    main_page_summary = soup.select('app-rapid-review-list .text-right')
    game.main_page_review_count = int(main_page_summary[0].text.split()[2])

    # Skip redundant scraping ----------------------------------------------------------------------
    try:
        if game.title in file_in_dict["OpenCritic Runners Up"].keys():
            # If no new reviews for a runner up, skip
            if file_in_dict["OpenCritic Runners Up"][game.title] == game.main_page_review_count:
                runner_up_dict[game.title] = game.main_page_review_count
                continue
        if file_in_dict[game.title][1] == game.main_page_review_count:
            if game.title in extra_lists.corrections_dict.keys():
                game.year = int(extra_lists.corrections_dict[game.title][1])
                game.title = extra_lists.corrections_dict[game.title][0]
            else:
                game.true_review_count = file_in_dict[game.title][1]
                game.score = file_in_dict[game.title][0]
                game.top_score = file_in_dict[game.title][2]
            if game.title in extra_lists.corrections_dict.keys():
                game.year = extra_lists.corrections_dict[game.title][1]
                game.title = extra_lists.corrections_dict[game.title][0]
            if game.year >= 2021:
                insert_into_true_list(game, true_list_gen9, true_list_gen9_titles)
            else:
                insert_into_true_list(game, true_list_gen8, true_list_gen8_titles)
            continue
    except:
        # If any errors when trying to skip, manually scrape game
        pass
    # --------------------------------------------------------------------------------------------
    # reviews = []                                          # Use to hand-check review aggregations (also uncomment two other sections)
    while not last_page:
        any_changes = True
        current_page += 1
        if current_page == 1:
            scrape_url = f"https://opencritic.com/{game.url}/reviews"
            first_page = True
        elif current_page > 1:
            scrape_url = f"https://opencritic.com/{game.url}/reviews?page={current_page}"
            first_page = False

        r = requests.get(scrape_url)
        soup = BeautifulSoup(r.content, "html.parser")

        review_rows = soup.select('app-review-table app-review-row')
        for review in review_rows:
            r_obj = review.select_one('.score-number-bold')
            if r_obj is None:
                # STAR SCORES
                star_list = review.select_one('app-score-display-raw').select('span .fas')
                empty_star_list = review.select_one('app-score-display-raw').select('span .far')
                if len(star_list) == 0:
                    # POSSIBLE LOST SCORES HERE
                    game.true_review_count += 1
                    continue
                else:
                    star_score, star_count = 0, 0
                    for star in star_list:
                        star_count += 1
                        if 'fa-star' in star['class']:
                            star_score += 1
                        elif 'fa-star-half-alt' in star['class']:
                            star_score += .5
                        else:
                            raise ConnectionError
                    star_count += len(empty_star_list)
                    review_score = star_score * (100 / star_count)
                    game.true_review_count += 1
            else:
                # NUMERIC SCORES (AND UNSCORED!!!)
                contains_char = False
                for char in r_obj.text:
                    if char.isupper() or char.islower():
                        contains_char = True
                if contains_char:
                    game.true_review_count += 1
                    continue
                else:
                    if '%' in r_obj.text:
                        # STANDARD NUMERIC SCORE
                        review_score = float(r_obj.text[:-1])
                        game.true_review_count += 1
                    else:
                        # PERCENTAGE SCORE
                        tokens = r_obj.text.split()
                        review_score = float(tokens[0]) * (100 / float(tokens[2]))
                        game.true_review_count += 1
            if review.select_one('.top-critic-info').select('div .fa'):
                top_score_sum += review_score
                top_score_count += 1
            # if review_score != 0:                         # Use to hand-check review aggregations (also uncomment two other sections)
            #     reviews += [review_score]
            score_sum += review_score
            score_count += 1
        nav_buttons = soup.select('.btn')
        if len(nav_buttons) != 4 and not first_page:
            last_page = True
    if score_count >= 20:
        game.score = score_sum / score_count
        # if game.title == "Celeste":                       # Use to hand-check review aggregations (also uncomment two other sections)
        #     print_review_score_counts(reviews)
        #     print(reviews)
        #     print(game.score)
        #     exit()
        game.top_score = top_score_sum / top_score_count
        if game.title in extra_lists.corrections_dict.keys():
            game.year = int(extra_lists.corrections_dict[game.title][1])
            game.title = extra_lists.corrections_dict[game.title][0]
        if game.year >= 2021:
            insert_into_true_list(game, true_list_gen9, true_list_gen9_titles)
        else:
            insert_into_true_list(game, true_list_gen8, true_list_gen8_titles)
        winner_names.append(game.title)
    if game.title not in winner_names:
        runner_up_dict[game.title] = game.main_page_review_count

mid_time = time.time()
minutes, seconds = divmod(datetime.timedelta(seconds=(mid_time - start_time)).seconds, 60)
print(f"Scraping process took {minutes} minutes and {seconds} seconds.")

# Write Final Output To Google Sheets
if not any_changes:
    end_time = time.time()
    minutes, seconds = divmod(datetime.timedelta(seconds=(end_time - start_time)).seconds, 60)
    print("No changes, so it's done!")
    exit()
print("Writing to Google Sheets...")
worksheet_gen8 = sheet.worksheet("title", "8th Generation (2013 - 2020)")
x_char_list = worksheet_gen8.get_col(9, include_tailing_empty=False)[1:51]
x_name_list = worksheet_gen8.get_col(2, include_tailing_empty=False)[1:51]
for i in range(len(x_char_list)):
    if not x_char_list[i]:
        x_name_list[i] = ""
x_list = [i for i in x_name_list if i != ""]
worksheet_gen8.clear()
worksheet_gen8.cell("A1").set_text_format("bold", True).value = "Rank"
worksheet_gen8.cell("B1").set_text_format("bold", True).value = "Title"
worksheet_gen8.cell("C1").set_text_format("bold", True).value = "Score"
worksheet_gen8.cell("D1").set_text_format("bold", True).value = "Top Critics"
worksheet_gen8.cell("E1").set_text_format("bold", True).value = "Change"
worksheet_gen8.cell("F1").set_text_format("bold", True).value = "Reviews"
worksheet_gen8.cell("G1").set_text_format("bold", True).value = "Errors?"
worksheet_gen8.cell("H1").set_text_format("bold", True).value = "Year"
worksheet_gen8.cell("I1").set_text_format("bold", True).value = 'Completed (Add "X")'
rank_counter_gen8 = 1
update_ranges, update_values = [], []

for game in true_list_gen8:
    if game.title not in file_in_dict.keys():
        change_text = ("New", 0)
    else:
        if float(file_in_dict[game.title][0]) - float(game.score) == 0:
            change_text = "0"
        elif float(file_in_dict[game.title][0]) - float(game.score) < 0:
            change_text = f"+{abs(float(file_in_dict[game.title][0]) - float(game.score))}"
        else:
            change_text = f"-{abs(float(file_in_dict[game.title][0]) - float(game.score))}"
    update_ranges.append(f"A{rank_counter_gen8 + 1}:I{rank_counter_gen8 + 1}")
    update_values.append([[
        rank_counter_gen8,
        game.title,
        game.score,
        f"+{(game.top_score - game.score):.2f}" if game.score < game.top_score else f"-{(game.score - game.top_score):.2f}",
        "New" if game.title not in file_in_dict.keys() else (change_text),
        game.true_review_count,
        f"{game.true_review_count}/{game.main_page_review_count}" if game.true_review_count != game.main_page_review_count else "No",
        int(game.year),
        "X" if game.title in x_list else ""]])
    worksheet_gen8.add_conditional_formatting(f"B{rank_counter_gen8 + 1}", f"B{rank_counter_gen8 + 1}", "CUSTOM_FORMULA", {"text_format" : {"bold" : True, "italic" : True}}, condition_values=[f'=I{rank_counter_gen8 + 1}=""'])
    file_out_dict[game.title] = [game.score, game.true_review_count, game.top_score]
    rank_counter_gen8 += 1
    if rank_counter_gen8 > num_of_games:
        cutoff_score = game.score
        break
worksheet_gen8.update_values_batch(update_ranges, update_values)
# Individual Year Progress
worksheet_gen8.cell(f"F{rank_counter_gen8 + 3}").formula = f'=CONCATENATE("2013: ", COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2013", I2:I{rank_counter_gen8 + 1}, "=X"), "/", COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2013"), " (", ROUND((COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2013", I2:I{rank_counter_gen8 + 1}, "=X")/COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2013"))*100), "%)")'
worksheet_gen8.cell(f"G{rank_counter_gen8 + 3}").formula = f'=CONCATENATE("2014: ", COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2014", I2:I{rank_counter_gen8 + 1}, "=X"), "/", COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2014"), " (", ROUND((COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2014", I2:I{rank_counter_gen8 + 1}, "=X")/COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2014"))*100), "%)")'
worksheet_gen8.cell(f"H{rank_counter_gen8 + 3}").formula = f'=CONCATENATE("2015: ", COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2015", I2:I{rank_counter_gen8 + 1}, "=X"), "/", COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2015"), " (", ROUND((COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2015", I2:I{rank_counter_gen8 + 1}, "=X")/COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2015"))*100), "%)")'
worksheet_gen8.cell(f"I{rank_counter_gen8 + 3}").formula = f'=CONCATENATE("2016: ", COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2016", I2:I{rank_counter_gen8 + 1}, "=X"), "/", COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2016"), " (", ROUND((COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2016", I2:I{rank_counter_gen8 + 1}, "=X")/COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2016"))*100), "%)")'
worksheet_gen8.cell(f"F{rank_counter_gen8 + 4}").formula = f'=CONCATENATE("2017: ", COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2017", I2:I{rank_counter_gen8 + 1}, "=X"), "/", COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2017"), " (", ROUND((COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2017", I2:I{rank_counter_gen8 + 1}, "=X")/COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2017"))*100), "%)")'
worksheet_gen8.cell(f"G{rank_counter_gen8 + 4}").formula = f'=CONCATENATE("2018: ", COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2018", I2:I{rank_counter_gen8 + 1}, "=X"), "/", COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2018"), " (", ROUND((COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2018", I2:I{rank_counter_gen8 + 1}, "=X")/COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2018"))*100), "%)")'
worksheet_gen8.cell(f"H{rank_counter_gen8 + 4}").formula = f'=CONCATENATE("2019: ", COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2019", I2:I{rank_counter_gen8 + 1}, "=X"), "/", COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2019"), " (", ROUND((COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2019", I2:I{rank_counter_gen8 + 1}, "=X")/COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2019"))*100), "%)")'
worksheet_gen8.cell(f"I{rank_counter_gen8 + 4}").formula = f'=CONCATENATE("2020: ", COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2020", I2:I{rank_counter_gen8 + 1}, "=X"), "/", COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2020"), " (", ROUND((COUNTIFS(H2:H{rank_counter_gen8 + 1}, "=2020", I2:I{rank_counter_gen8 + 1}, "=X")/COUNTIF(H2:H{rank_counter_gen8 + 1}, "=2020"))*100), "%)")'
worksheet_gen8.cell(f"I{rank_counter_gen8 + 1}").formula = f'=CONCATENATE("Progess: ", COUNTIF(I2:I{rank_counter_gen8}, "=X"), "/{rank_counter_gen8 - 1} (", ROUND((COUNTIF(I2:I{rank_counter_gen8}, "=X")/{rank_counter_gen8 - 1})*100), "%)")'
worksheet_gen8.cell(f"B{rank_counter_gen8 + 3}").value = runtime_datestring

# 9th Generation Begins Below
worksheet_gen9 = sheet.worksheet("title", "9th Generation (2021 - Present)")
x_char_list = worksheet_gen9.get_col(9, include_tailing_empty=False)[1:51]
x_name_list = worksheet_gen9.get_col(2, include_tailing_empty=False)[1:51]
for i in range(len(x_char_list)):
    if not x_char_list[i]:
        x_name_list[i] = ""
x_list = [i for i in x_name_list if i != ""]
worksheet_gen9.clear()
worksheet_gen9.cell("A1").set_text_format("bold", True).value = "Rank"
worksheet_gen9.cell("B1").set_text_format("bold", True).value = "Title"
worksheet_gen9.cell("C1").set_text_format("bold", True).value = "Score"
worksheet_gen9.cell("D1").set_text_format("bold", True).value = "Top Critics"
worksheet_gen9.cell("E1").set_text_format("bold", True).value = "Change"
worksheet_gen9.cell("F1").set_text_format("bold", True).value = "Reviews"
worksheet_gen9.cell("G1").set_text_format("bold", True).value = "Errors?"
worksheet_gen9.cell("H1").set_text_format("bold", True).value = "Year"
worksheet_gen9.cell("I1").set_text_format("bold", True).value = 'Completed (Add "X")'
rank_counter_gen9 = 1
update_ranges, update_values = [], []
cutoff_passed = False
cutoff_offset = 0
cutoff_point = 0
for game in true_list_gen9:
    if game.score < cutoff_score and cutoff_passed is False:
        cutoff_passed = True
        cutoff_offset = 1
        cutoff_point = rank_counter_gen9
        update_values.append([["", "", "", "", "", "", "", ""]])
        update_ranges.append(f"A{rank_counter_gen9 + 1}:I{rank_counter_gen9 + 1}")
    if game.title not in file_in_dict.keys():
        change_text = "New"
    else:
        if float(file_in_dict[game.title][0]) - float(game.score) == 0:
            change_text = "0"
        elif float(file_in_dict[game.title][0]) - float(game.score) < 0:
            change_text = f"+{abs(float(file_in_dict[game.title][0]) - float(game.score))}"
        else:
            change_text = f"-{abs(float(file_in_dict[game.title][0]) - float(game.score))}"
    update_ranges.append(f"A{rank_counter_gen9 + 1 + cutoff_offset}:I{rank_counter_gen9 + 1 + cutoff_offset}")
    update_values.append([[
        rank_counter_gen9,
        game.title,
        game.score,
        f"+{(game.top_score - game.score):.2f}" if game.score < game.top_score else f"-{(game.score - game.top_score):.2f}",
        "New" if game.title not in file_in_dict.keys() else (change_text),
        game.true_review_count,
        f"{game.true_review_count}/{game.main_page_review_count}" if game.true_review_count != game.main_page_review_count else "No",
        int(game.year),
        "X" if game.title in x_list else ""]])
    worksheet_gen9.add_conditional_formatting(f"B{rank_counter_gen9 + 1 + cutoff_offset}", f"B{rank_counter_gen9 + 1 + cutoff_offset}", "CUSTOM_FORMULA", {"text_format" : {"bold" : True, "italic" : True}}, condition_values=[f'=I{rank_counter_gen9 + 1 + cutoff_offset}=""'])
    file_out_dict[game.title] = [game.score, game.true_review_count, game.top_score]
    rank_counter_gen9 += 1
    if rank_counter_gen9 > 50:
        break
if cutoff_passed is True:
    formula_cutoff = cutoff_point
else:
    formula_cutoff = rank_counter_gen9
worksheet_gen9.update_values_batch(update_ranges, update_values)
# Individual Year Progress
worksheet_gen9.cell(f"F{rank_counter_gen9 + 3 + cutoff_offset}").formula = f'=CONCATENATE("2021: ", COUNTIFS(H2:H{formula_cutoff + 1}, "=2021", I2:I{formula_cutoff + 1}, "=X"), "/", COUNTIF(H2:H{formula_cutoff + 1}, "=2021"), " (", ROUND((COUNTIFS(H2:H{formula_cutoff + 1}, "=2021", I2:I{formula_cutoff + 1}, "=X")/COUNTIF(H2:H{formula_cutoff + 1}, "=2021"))*100), "%)")'
worksheet_gen9.cell(f"G{rank_counter_gen9 + 3 + cutoff_offset}").formula = f'=CONCATENATE("2022: ", COUNTIFS(H2:H{formula_cutoff + 1}, "=2022", I2:I{formula_cutoff + 1}, "=X"), "/", COUNTIF(H2:H{formula_cutoff + 1}, "=2022"), " (", ROUND((COUNTIFS(H2:H{formula_cutoff + 1}, "=2022", I2:I{formula_cutoff + 1}, "=X")/COUNTIF(H2:H{formula_cutoff + 1}, "=2022"))*100), "%)")'
worksheet_gen9.cell(f"H{rank_counter_gen9 + 3 + cutoff_offset}").formula = f'=CONCATENATE("2023: ", COUNTIFS(H2:H{formula_cutoff + 1}, "=2023", I2:I{formula_cutoff + 1}, "=X"), "/", COUNTIF(H2:H{formula_cutoff + 1}, "=2023"), " (", ROUND((COUNTIFS(H2:H{formula_cutoff + 1}, "=2023", I2:I{formula_cutoff + 1}, "=X")/COUNTIF(H2:H{formula_cutoff + 1}, "=2023"))*100), "%)")'
worksheet_gen9.cell(f"I{rank_counter_gen9 + 3 + cutoff_offset}").formula = f'=CONCATENATE("2024: ", COUNTIFS(H2:H{formula_cutoff + 1}, "=2024", I2:I{formula_cutoff + 1}, "=X"), "/", COUNTIF(H2:H{formula_cutoff + 1}, "=2024"), " (", ROUND((COUNTIFS(H2:H{formula_cutoff + 1}, "=2024", I2:I{formula_cutoff + 1}, "=X")/COUNTIF(H2:H{formula_cutoff + 1}, "=2024"))*100), "%)")'
worksheet_gen9.cell(f"F{rank_counter_gen9 + 4 + cutoff_offset}").formula = f'=CONCATENATE("2025: ", COUNTIFS(H2:H{formula_cutoff + 1}, "=2025", I2:I{formula_cutoff + 1}, "=X"), "/", COUNTIF(H2:H{formula_cutoff + 1}, "=2025"), " (", ROUND((COUNTIFS(H2:H{formula_cutoff + 1}, "=2025", I2:I{formula_cutoff + 1}, "=X")/COUNTIF(H2:H{formula_cutoff + 1}, "=2025"))*100), "%)")'
worksheet_gen9.cell(f"G{rank_counter_gen9 + 4 + cutoff_offset}").formula = f'=CONCATENATE("2026: ", COUNTIFS(H2:H{formula_cutoff + 1}, "=2026", I2:I{formula_cutoff + 1}, "=X"), "/", COUNTIF(H2:H{formula_cutoff + 1}, "=2026"), " (", ROUND((COUNTIFS(H2:H{formula_cutoff + 1}, "=2026", I2:I{formula_cutoff + 1}, "=X")/COUNTIF(H2:H{formula_cutoff + 1}, "=2026"))*100), "%)")'
worksheet_gen9.cell(f"H{rank_counter_gen9 + 4 + cutoff_offset}").formula = f'=CONCATENATE("2027: ", COUNTIFS(H2:H{formula_cutoff + 1}, "=2027", I2:I{formula_cutoff + 1}, "=X"), "/", COUNTIF(H2:H{formula_cutoff + 1}, "=2027"), " (", ROUND((COUNTIFS(H2:H{formula_cutoff + 1}, "=2027", I2:I{formula_cutoff + 1}, "=X")/COUNTIF(H2:H{formula_cutoff + 1}, "=2027"))*100), "%)")'
worksheet_gen9.cell(f"I{rank_counter_gen9 + 4 + cutoff_offset}").formula = f'=CONCATENATE("2028: ", COUNTIFS(H2:H{formula_cutoff + 1}, "=2028", I2:I{formula_cutoff + 1}, "=X"), "/", COUNTIF(H2:H{formula_cutoff + 1}, "=2028"), " (", ROUND((COUNTIFS(H2:H{formula_cutoff + 1}, "=2028", I2:I{formula_cutoff + 1}, "=X")/COUNTIF(H2:H{formula_cutoff + 1}, "=2028"))*100), "%)")'
worksheet_gen9.cell(f"I{rank_counter_gen9 + 1 + cutoff_offset}").formula = f'=CONCATENATE("Progess: ", COUNTIF(I2:I{formula_cutoff}, "=X"), "/{formula_cutoff - 1} (", ROUND((COUNTIF(I2:I{formula_cutoff}, "=X")/{formula_cutoff - 1})*100), "%)")'
worksheet_gen9.cell(f"B{rank_counter_gen9 + 3 + cutoff_offset}").value = runtime_datestring

print("Done!")

end_time = time.time()
minutes, seconds = divmod(datetime.timedelta(seconds=(end_time - start_time)).seconds, 60)
worksheet_gen8.cell(f"B{rank_counter_gen8 + 4}").value = f"Completed in {minutes} minutes and {seconds} seconds"
worksheet_gen9.cell(f"B{rank_counter_gen9 + 4 + cutoff_offset}").value = f"Completed in {minutes} minutes and {seconds} seconds"
file_out_dict["OpenCritic Runners Up"] = runner_up_dict

with open("opencritic_hall_of_fame.json", "w") as f:
    json.dump(file_out_dict, f)