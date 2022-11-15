import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps
from splitwise import Splitwise
import config as Config

def get_access_token():
    sObj = Splitwise(Config.consumer_key,Config.consumer_secret)
    sObj.setAccessToken(session['access_token'])
    return sObj

def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

# Function to add an element to error list
def add_to_error_list(error_type : str, element_id : int, error_master : dict ): #error_master = error_master means by default we import this dict with the same name
    """ Add an element to error list, indicating error type and element ID """
    error_master[error_type]['error_list'].append(str(element_id))
    return element_id 

# Function to build the error message
def new_error_msg(error_type : str, error_master : dict):
    """ Adds error type (error description + list of items) to the overall error_message"""
    error_dict = error_master[error_type]
    if error_dict['element_type'] == 'general':
        message = error_dict['message']+ ".\n"
    else:
        error_list_str = ', '.join(error_dict['error_list'])
        message = error_dict['message'] + " (" + error_dict['element_type'] + " " + error_list_str + ").\n"
    return message

def map_sw_info(list_names : list, up_users):
    list_ids = [member.final_id for member in up_users]
        

def label_race (row):
   if row['eri_hispanic'] == 1 :
      return 'Hispanic'
   if row['eri_afr_amer'] + row['eri_asian'] + row['eri_hawaiian'] + row['eri_nat_amer'] + row['eri_white'] > 1 :
      return 'Two Or More'
   if row['eri_nat_amer'] == 1 :
      return 'A/I AK Native'
   if row['eri_asian'] == 1:
      return 'Asian'
   if row['eri_afr_amer']  == 1:
      return 'Black/AA'
   if row['eri_hawaiian'] == 1:
      return 'Haw/Pac Isl.'
   if row['eri_white'] == 1:
      return 'White'
   return 'Other'
