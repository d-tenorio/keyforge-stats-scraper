# -*- coding: utf-8 -*-
"""
@author: David Tenorio

v0.11

Written in Python 2.7.X, mainly to maintain compatibility with PyInstaller

executable created using command 
pyinstaller --onefile main.py -n keyforge_stats_scraper_exe
"""

from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup
import sys
import codecs
import json
import urllib2

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
    
def get_stats(s):
    """
    gets the stats for a keyforge deck: ABCE + different types of cards
    """
    first_line, second_line, third_line = [],[],[]
    
    #get the stats of interest, splits them into different lists
    #to allow for readability later
    for i, e in enumerate(s.select('li')):
        curr_line = e.text.split(" ")

        if i < 4:    
            first_line.append(curr_line)
            
        elif i >= 4 and i < 7:
            second_line.append(curr_line)
        
        elif i >= 7 and i < 9:
                third_line.append(curr_line)
      
    #temporary list to hold each line
    temp = []
    
    #now, go through each line and format it properly
    
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
    
    line_2 = "| ".join(temp)
    
    #third line: E and the consistency
    temp = []
    for i,e in enumerate(third_line):
        if i == 0:
            this_line = [ABCE_dict[3],e[1],e[2]]
        else:
            this_line = ["Cons:",e[1]]
        temp.append(" ".join(this_line))
            
    line_3 = "| ".join(temp)
    
    #now, return the three lines separated into new lines
    return "\r\n".join([line_1,line_2,line_3])
        
def get_cards(s):
    """
    gets the specific cards in the decks along with the houses and returns 
    a nicely formatted string for printing containing the contents of the deck
    """

    cards = []
    
    #amounts and names of each card
    for i, e in enumerate(s.select('td')):
        if (i-1) % 6 == 0 or (i-1) % 6 == 1:
            cards.append(e.text)
            
    #rarity + houses
    rarities = []
    poss_houses = ["Brobnar","Dis","Logos","Mars","Sanctum","Shadows","Untamed"]
    houses_uniq = set()
    houses = []
   
    mav_count = 0 
    
    #separate the cards from the houses
    for i, e in enumerate(s.select('td > img')):
        if e.attrs['alt'] in poss_houses:
            
            last_house_index = i            
            
            if e.attrs['alt'] not in houses_uniq:
                houses_uniq.add(e.attrs['alt'])
                houses.append(e.attrs['alt'])    
    
        else:
            if i - last_house_index == 1:            
                rarities.append(e.attrs['alt'])
            else:
                rarities[-1] = "MAV"
                mav_count += 1
            
    
    cards_with_rarities = []
    
    counter_rarity = 0
    
    #getting the right amount of copies of each card
    for i,e in enumerate(cards):
        if i % 2 == 1:
            for j in range(int(cards[i-1])):
                cards_with_rarities.append(": ".join([rarities[counter_rarity][0],e]))
            counter_rarity += 1
    
    #now, insert the houses
    house_indices = [0,13,26]
    for i,house in enumerate(houses):
        cards_with_rarities.insert(house_indices[i],"\r\n" + house)
        
    return "\r\n".join(cards_with_rarities)


def get_link(s):
    """
    returns the original KeyForgeGame link
    """
    return s.select("div > h5 > a")[0]['href']
   
def get_name(s):
    """
    returns the name of the deck
    """
    return s.select("div > h5 > a")[0].text

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
    
    ans = []
    
    #find the proper key-value pair in the JSON
    for e in titles_AERC:
        val = str(data[camel_case(e)])
        ans.append(": ".join([e,val]) )
        
    for e in titles_SAS:
        val = data[e.lower()+"Rating"]
        if e == "Antisynergy": #make sure the antisynergy is negative!
            val = -1*val
        val = str(val)
        ans.append(": ".join([e,val]) )
        
    ans = "\r\n".join(ans)
    return ans
    
def analyze_deck(deck_link):
    """
    takes in a string containing a keyforge-compendium link and 
    outputs desirable statistics
    of that deck link in a nicely formatted string
    """
    
    #unique_ID from that link
    uniq_ID = deck_link[38:]
    
    #now, get the html from the Compendium page
    raw_html = simple_get(deck_link)
    
    #make it parsable
    html = BeautifulSoup(raw_html, 'html.parser')
    
    #and get all of the relevant ABCE and card information from it
    stats = get_stats(html)
    output = get_cards(html)
    link = get_link(html)
    name = get_name(html)
    
    #use that unique_ID to access decksofkeyforge
    deck_link_DoKF = "https://decksofkeyforge.com/api/decks/" + uniq_ID + "/simple"

    #now, get the relevant SAS information
    SAS = get_SAS(deck_link_DoKF)
    
    #print it all out 
    print "\r"
    print "\r\nDeck name:", name
    print "\r"
    print "\r"
    print stats
    print "\r"
    print "\r"
    print output
    print "\r"
    print "\r"
    print "SAS Info\r\n\r\n", SAS
    print "\r"
    print "\r"
    print "KeyForgeGame:", link
    print "\r"
    print "KeyForge-Compendium:", deck_link
    print "\r"
    print "Decks of KeyForge:", "https://decksofkeyforge.com/decks/" + uniq_ID
    print "\r"
    print "\r"


def main():
    """
    This script searches for a properly named .txt file that contains
    a list of keyforge-compendium links, one per line
    
    For each link, main.py parses the html from that link and obtains important deck information (metrics + cards)
    
    It then outputs all of that information to a .txt file saved in the same directory as this file,
    deck_info_output.txt. deck_info_output.txt will also hold any error information that might occur.
    
    """
    
    #save the location of stdout
    old_stdout = sys.stdout
    
    #find the file
    
    #from here, save all output to text file
    #note the use of codecs to allow for the use of Unicode utf-8 encoding
    sys.stdout = codecs.open(r"./deck_info_output.txt", "w", encoding="utf-8")   
    
    try: 
        text_file = open("kf_deck_links.txt", "r")
        lines = text_file.readlines()
        text_file.close()
    except:
        print "\r\nERROR when attempting to read in kf_deck_links.txt, please make sure the file is in the same directory as the executable and follows the desired format"
    

    try:
        print "Beginning deck analysis...\r"
        for i,deck_link in enumerate(lines):
          
            print "Deck number", i+1, "of this run"
            print "\r\nRunning keyforge_scraper using the link: \r\n", deck_link
            
            #remove any newline characters that may have slipped in
            clean_link = deck_link.strip("\n")
            clean_link = clean_link.strip("\r")
            analyze_deck(clean_link)
        
            print ("----------------------------------------------\r\n")
            
    except:
        #in case there was an error, print a debugging message and reset the std out
        print "\r\n\r\nERROR while analyzing. \r\nPlease make sure the link entered was an unmodified keyforge-compendium https:// link with no extra characters or spaces." 
        sys.stdout = old_stdout
        return
    
    print "All done! Analyzed", i+1, "decks in total."
    print "\r"
    #reset stdout
    sys.stdout = old_stdout
        
        
if __name__== "__main__":
    main()


