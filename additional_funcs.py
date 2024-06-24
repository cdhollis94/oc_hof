from msilib.schema import Error
from bs4 import BeautifulSoup
import requests
import pygsheets

def specific_game(title, game_number):
    """Example: python3 hof_scrape.py -s "Xenoblade Chronicles 3: Future Redeemed" -n 14872"""
    parsed_title = title.replace(" ", "-").replace(":","").lower()
    client = pygsheets.authorize(service_account_file="opencritic-hall-of-fame-75785a168121.json")
    sheet = client.open("opencritic_hall_of_fame")
    worksheet_gen8 = sheet.worksheet("title", "8th Generation (2013 - 2020)")

    last_page = False
    current_page = 0
    score_sum, score_count = 0, 0
    while not last_page:
        current_page += 1
        if current_page == 1:
            scrape_url = f"https://opencritic.com/game/{game_number}/{parsed_title}/reviews"
            first_page = True
        elif current_page > 1:
            scrape_url = f"https://opencritic.com/game/{game_number}/{parsed_title}/reviews?page={current_page}"
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
                            raise Error
                    star_count += len(empty_star_list)
                    review_score = star_score * (100 / star_count)
            else:
                # NUMERIC SCORES (AND UNSCORED!!!)
                contains_char = False
                for char in r_obj.text:
                    if char.isupper() or char.islower():
                        contains_char = True
                if contains_char:
                    continue
                else:
                    if '%' in r_obj.text:
                        # STANDARD NUMERIC SCORE
                        review_score = float(r_obj.text[:-1])
                    else:
                        # PERCENTAGE SCORE
                        tokens = r_obj.text.split()
                        review_score = float(tokens[0]) * (100 / float(tokens[2]))
            score_sum += review_score
            score_count += 1
        nav_buttons = soup.select('.btn')
        if len(nav_buttons) != 4 and not first_page:
            last_page = True
    final_score = score_sum / score_count

    worksheet_gen8.cell("B57").set_text_format("italic", True).value = title
    worksheet_gen8.cell("C57").set_text_format("italic", True).value = final_score