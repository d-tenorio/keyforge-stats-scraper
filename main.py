# -*- coding: utf-8 -*-
"""
@author: David Tenorio

v0.40

Written in Python 2.7.X, mainly to maintain compatibility with PyInstaller

executable created using command 
pyinstaller --onefile main.py -n keyforge_stats_scraper_exe
"""

from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup
import codecs, sys
import json
import urllib2
import unicodecsv as csv
import re

# parts of this code taken from https://realpython.com/python-web-scraping-practical-introduction/
# and adapted for this use

def simple_get(url):
    """
    Attempts to get the content at `url` by making an HTTP GET request.
    If the content-type of response is some kind of HTML/XML, return the
    text content, otherwise return None.
    """
    try:
        with closing(get(url, stream=True)) as resp:
            if is_good_response(resp):
                return resp.content
            else:
                return None

    except RequestException as e:
        log_error('Error during requests to {0} : {1}'.format(url, str(e)))
        return None


def is_good_response(resp):
    """
    Returns True if the response seems to be HTML, False otherwise.
    """
    content_type = resp.headers['Content-Type'].lower()
    return (resp.status_code == 200 
            and content_type is not None 
            and content_type.find('html') > -1)


def log_error(e):
    """
    It is always a good idea to log errors. 
    This function just prints them, but you can
    make it do anything.
    """
    print(e)

#end of code taken from https://realpython.com/python-web-scraping-practical-introduction/

def weird_character_removal(s):
    """takes in a string, s, and replaces any weird Unicode characters with the proper output"""
    s = re.sub(u'\u201c','"',s)
    s = re.sub(u'\u201d','"',s)
    s = re.sub(u'\u2019','\'',s)
    return s

def get_name(J):
    """
    takes in a json from a keyforgegame API call, J, and returns the name of the deck
    """
    name = J['data']['name']
    #get rid of Unicode quotation marks, which come out weird in Unicode
    name = weird_character_removal(name)
    return [name]

def get_comp(J):
    """
    takes in a json from a keyforgegame API call, J, and returns the competitive stats
    for the deck (chains, power level, wins, losses)
    """
    #find the competitive stats in the html
    data = J['data']
    
    titles = ['Power Level','Chains','Wins','Losses']
    
    output = []
    for title in titles:
        api_key = "_".join(title.lower().split(" "))
        api_val = str(int(data[api_key]))
        
        output.append(": ".join([title,api_val]))

    return output


def get_abce(s):
    """
    gets the stats for a keyforge deck: ABCE + different types of cards
    """
    first_line, second_line, third_line = [],[],[]
    
    #get the stats of interest, splits them into different lists
    #to allow for readability later
    for i, e in enumerate(s.select('li')):
        curr_line = e.text.split(" ")

        if i < 4:
            #different formatting needed for these values
            curr_line = e.text.split("\n")
            curr_line = [str(int(curr_line[1])), curr_line[2].strip(' ')]
            first_line.append(curr_line)
            
        elif i >= 4 and i < 7:
            second_line.append(curr_line)
        
        elif i >= 7 and i < 9:
                third_line.append(curr_line)
      
    #temporary list to hold each line
    temp = []
    
    #go through each line and format it properly
    #first line: breakdown of Creatures/Actions/Artifacts/Upgrades
    for e in first_line:
        e.reverse()
        temp.append(": ".join(e))
    
    line_1 = " ".join(temp)
    
    #get the proper letter for each stat
    ABCE_dict = {0:"A:",1:"B:",2:"C:",3:"E:"} 
    
    #second line: A, B, and C
    temp = []
    for i,e in enumerate(second_line):
        if i == 2:
            this_line = [ABCE_dict[i],e[2],e[3]]
        else:
            this_line = [ABCE_dict[i],e[1],e[2]]
        temp.append(" ".join(this_line))
    
    line_2 = " | ".join(temp)
    
    #third line: E and the consistency
    temp = []
    for i,e in enumerate(third_line):
        if i == 0:
            this_line = [ABCE_dict[3],e[1],e[2]]
        else:
            this_line = ["Cons:",e[1]]
        temp.append(" ".join(this_line))
            
    line_3 = " | ".join(temp)
    
    #now, return the three lines separated into new lines
    return [line_1,line_2,line_3]

def camel_case(s):
    parts = s.split(" ")
    parts[0] = parts[0].lower()
    
    return "".join(parts)

def get_SAS(s):
    """
    takes in a decksofkeyforge link, loads the JSON containing deck information,
    and returns the important SAS stats
    """

    #now, get the json from decksofkeyforge
    data = json.load(urllib2.urlopen(s))
    
    titles_AERC = ["Amber Control", "Expected Amber","Artifact Control","Creature Control"]
    titles_SAS = ["Cards","Synergy","Antisynergy","SAS"]    
    
    output = ["SAS Info"]
    
    #find the proper key-value pair in the JSON
    for e in titles_AERC:
        val = str(int(round(data['deck'][camel_case(e)])))
        output.append(": ".join([e,val]) )
        
    for e in titles_SAS:
        val = data['deck'][e.lower()+"Rating"]
        if e == "Antisynergy": #make sure the antisynergy is negative!
            val = -1*val
        val = str(int(round(val)))
        output.append(": ".join([e,val]) )

    return output
        
def get_cards(J):
    """
    takes in a json from a keyforgegame API call, J,
    gets the specific cards in the decks along with the houses and returns 
    a nicely formatted string for printing containing the contents of the deck
    """
    #locate the section of the JSON we are interested in
    data = J['data']['_links']
    
    #dictionary to hold each card, with the house as the key and a list
    #of cards as the val
    cards = {}
    
    #initialize the house
    for i in range(3):
        house = data['houses'][i]
        cards[house] = []
    
    #dictionary to hold how many times each card appears
    card_ids = {}
    for i in range(36):
        card_id = data['cards'][i]
        if card_id in card_ids:
            card_ids[card_id] += 1
        else:
            card_ids[card_id] = 1

    
    card_data = J['_linked']['cards']
    
    for i in range(36):
        #keep going until we run out of cards
        try:
            curr = card_data[i]
            
            #get interesting stats
            name = curr['card_title']
            #get rid of strange Unicode characters, which come out weird in Unicode
            name = weird_character_removal(name)
            
            curr_house = curr['house']
            rarity = curr['rarity'][0]
            if curr['is_maverick']:
                rarity = 'M'
            exp = curr['expansion']
            curr_id = curr['id']
            
            #then add the right number of copies of this card
            #to our list of cards
            num_copies = card_ids[curr_id]
            line = ": ".join([rarity,name])
            for _ in range(num_copies):
                cards[curr_house].append(line)
            
        #if we run out of cards, stop
        except:
            break
        
    output = []
    
    for house in sorted(cards.keys()):
        output.append(house)
        for card in cards[house]:
            output.append(card)
    
    return output
    


    
def analyze_decks(deck_links,fname):
    """
    takes in a string containing a keyforge-compendium, 
    keyforgegame, or decksofkeyforge link and 
    writes desirable statistics of the corresponding deck to a .csv file
    """
    
    with open(fname, mode='wb') as f:
        w = csv.writer(f, encoding='utf-8')
        
        for j,deck_link in enumerate(deck_links):
            print "\r"
            print "\r\nDeck number", j+1, "of this run"

            #take away any  newline characters
            deck_link = deck_link.strip("\n")
            deck_link = deck_link.strip("\r")
            
            #strip the ID from the URL given, regardless of type
            ID_begin = deck_link.rfind('/')
            
            uniq_ID = deck_link[ID_begin+1:]
            
            compendium_link = r'https://keyforge-compendium.com/decks/' + uniq_ID
            
            print "\r\nRunning keyforge_scraper using the deck ID: \r\n", uniq_ID
            
            w.writerow(["Deck number:",str(j+1)])
            
            #use the KeyforgeGame API to get a lot of ifo
            kfg_api = r"https://www.keyforgegame.com/api/decks/" + uniq_ID + r"/?links=cards,notes"
            
            #need to simulate a browser for the kfg API to work
            headers = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:62.0) Gecko/20100101 Firefox/65.0'}
            params = { 'links': 'cards'}
            
            kfg_api_html = get(kfg_api, headers=headers, params=params)
            kfg_data = kfg_api_html.json()
            
            #start by getting the name and competitive info
            name = get_name(kfg_data)
            w.writerow(name)
            w.writerow([" "])
            
            w.writerow(["Competitive Stats"])
            compete_stats = get_comp(kfg_data)
            for stat in compete_stats:
                w.writerow([stat])
            w.writerow([" "])
            
            #now, get the html from the Compendium page
            raw_html = simple_get(compendium_link)
        
            #make it parsable
            compendium_html = BeautifulSoup(raw_html, 'html.parser')
        
            #continue on to the ABCE stats and different card types
            abce_stats = get_abce(compendium_html)
            for stat in abce_stats:
                w.writerow([stat])
                    
            #now, use the deck's unique_ID to access decksofkeyforge
            dokf_link = "https://decksofkeyforge.com/api/decks/" + uniq_ID

            #get the relevant SAS information
            SAS = get_SAS(dokf_link)
            w.writerow([" "])
            for stat in SAS:
                w.writerow([stat])
                
            #write out all of the cards + their rarities + house
            w.writerow([" "])
            
            cards = get_cards(kfg_data)
            for card in cards:
                w.writerow([card])
            
            #finally, print out all relevant links
            w.writerow([" "])
            w.writerow(["Links"])
            w.writerow(["KeyForgeGame:", r"https://www.keyforgegame.com/deck-details/" + uniq_ID])
            w.writerow(["KeyForge-Compendium:", deck_link])
            w.writerow(["Decks of KeyForge:", r"https://decksofkeyforge.com/decks/" + uniq_ID])
            w.writerow([" "])

def main():
    """
    This script searches for a properly named .txt file that contains
    a list of deck links, one per line
    
    For each link, main.py parses the html from that link and obtains important deck information (metrics + cards)
    
    It then outputs all of that information to a .csv file saved in the same directory as this file,
    deck_info_output.csv. kss_debug.txt will also hold any error information that might occur.
    
    """
    
    #save the location of stdout
    old_stdout = sys.stdout
    
    #from here, save all printed output to text file
    #note the use of codecs to allow for the use of Unicode utf-8 encoding
    sys.stdout = codecs.open(r"./kss_debug.txt", "w", encoding="utf-8-sig")   
    
    try: 
        text_file = open("kf_deck_links.txt", "r")
        deck_links = text_file.readlines()
        text_file.close()

    except:
        print "\r\nERROR when attempting to read in kf_deck_links.txt, please make sure the file is in the same directory as the executable and follows the desired format"
        sys.stdout = old_stdout
        return 


    print "Beginning deck analysis...\r"
    
    fname = 'deck_info_output.csv'
    try:
        analyze_decks(deck_links,fname)    
    
    #in case there was an error, print a debugging message and reset stdout
    except:
        print "\r\n\r\nERROR while analyzing. \r\nPlease make sure the link entered was an unmodified keyforge-compendium https:// link with no extra characters or spaces." 
        sys.stdout = old_stdout
        return 

    print "\r\n\r\nAll done! Analyzed", len(deck_links), "decks in total."
    print "\r"
    
    #reset stdout
    sys.stdout = old_stdout
        
        
if __name__== "__main__":
    main()


