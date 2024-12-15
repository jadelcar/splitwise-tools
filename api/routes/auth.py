from splitwise import Splitwise
from starlette.requests import Request

from core.config.settings import get_settings

settings = get_settings()
URL = f"http://{settings.APP_HOST}:{settings.APP_PORT}"

def get_access_token(request: Request):
    """ Obtain Splitwise object (only if there is an access token """
    # try:
    sObj = Splitwise(settings.CONSUMER_KEY, settings.CONSUMER_SECRET)
    # except:
    # raise Exception("Could not obtain the Splitwise object, consumer key/secret has expired")
    # try:
    sObj.setOAuth2AccessToken(request.session.get('access_token'))
    return sObj
    # except:
    # raise Exception("Could not set access token. Maybe the user has not authorized Splitwise or the session has expired")
        