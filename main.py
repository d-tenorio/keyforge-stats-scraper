# -*- coding: utf-8 -*-
"""
@author: David Tenorio

v0.30

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
 
def get_name(s):
    """
    returns the name of the deck
    """
    name = s.select("div > h5 > a")[0].text
    #get rid of Unicode quotation marks, which come out weird in Unicode
    name = re.sub(u'\u201c','"',name)
    name = re.sub(u'\u201d','"',name)
    return [name]

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
    
    ans = ["SAS Info"]
    
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

    return ans
        
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
        cards_with_rarities.insert(house_indices[i], house)

    return cards_with_rarities


def get_link(s):
    """
    returns the original KeyForgeGame link
    """
    return s.select("div > h5 > a")[0]['href']
   

    
def analyze_decks(deck_links,fname):
    """
    takes in a string containing a keyforge-compendium link and 
    writes desirable statistics of that deck link to a .csv file
    """
    
    with open(fname, mode='wb') as f:
        w = csv.writer(f, encoding='utf-8')
        
        for j,deck_link in enumerate(deck_links):
            print "\r"
            print "\r\nDeck number", j+1, "of this run"
            print "\r\nRunning keyforge_scraper using the link: \r\n", deck_link
            
            w.writerow(["Deck number:",str(j+1)])
            
            deck_link = deck_link.strip("\n")
            deck_link = deck_link.strip("\r")
            
            #unique_ID from that link
            uniq_ID = deck_link[38:]
        
            #now, get the html from the Compendium page
            raw_html = simple_get(deck_link)
        
            #make it parsable
            html = BeautifulSoup(raw_html, 'html.parser')
        
            #begin extracting information, starting with the deck name
            name = get_name(html)
            w.writerow(name)
            
            #continue on to the ABCE stats and different card types
            stats = get_stats(html)
            for stat in stats:
                w.writerow([stat])
                    
            #now, use the deck's unique_ID to access decksofkeyforge
            deck_link_DoKF = "https://decksofkeyforge.com/api/decks/" + uniq_ID + "/simple"
        
            #get the relevant SAS information
            SAS = get_SAS(deck_link_DoKF)
            w.writerow([" "])
            for stat in SAS:
                w.writerow([stat])
                
            #write out all of the cards + their rarities + house
            w.writerow([" "])
            cards = get_cards(html)
            for card in cards:
                #get rid of Unicode quotation marks, which come out weird when writing out
                card = re.sub(u'\u201c','"',card)
                card = re.sub(u'\u201d','"',card)
                w.writerow([card])
            
            #finally, print out all relevant links
            link = get_link(html)
            w.writerow(["Links"])
            w.writerow(["KeyForgeGame:", link])
            w.writerow(["KeyForge-Compendium:", deck_link])
            w.writerow(["Decks of KeyForge:", "https://decksofkeyforge.com/decks/" + uniq_ID])
            w.writerow([" "])

def main():
    """
    This script searches for a properly named .txt file that contains
    a list of keyforge-compendium links, one per line
    
    For each link, main.py parses the html from that link and obtains important deck information (metrics + cards)
    
    It then outputs all of that information to a .csv file saved in the same directory as this file,
    deck_info_output.csv. kss_debug.txt will also hold any error information that might occur.
    
    """
    
    #save the location of stdout
    old_stdout = sys.stdout
    
    #find the file
    
    #from here, save all printed output to text file
    #note the use of codecs to allow for the use of Unicode utf-8 encoding
    sys.stdout = codecs.open(r"./kss_debug.txt", "w", encoding="utf-8-sig")   
    
    try: 
        text_file = open("kf_deck_links.txt", "r")
        deck_links = text_file.readlines()
        text_file.close()
    except:
        print "\r\nERROR when attempting to read in kf_deck_links.txt, please make sure the file is in the same directory as the executable and follows the desired format"
    


    print "Beginning deck analysis...\r"
    
    fname = 'deck_info_output.csv'
    try:
        analyze_decks(deck_links,fname)    
    
    
    #in case there was an error, print a debugging message and reset the std out
    except:
        print "\r\n\r\nERROR while analyzing. \r\nPlease make sure the link entered was an unmodified keyforge-compendium https:// link with no extra characters or spaces." 
        sys.stdout = old_stdout
        return
    
    print "\r\nAll done! Analyzed", len(deck_links), "decks in total."
    print "\r"
    
    #reset stdout
    sys.stdout = old_stdout
        
        
if __name__== "__main__":
    main()


