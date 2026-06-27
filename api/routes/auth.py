from splitwise import Splitwise
from starlette.requests import Request
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from core.config.settings import Settings, get_settings
from core.exceptions import handlers
from core.templates import templates
from fastapi.logger import logger



from core.config.settings import get_settings

router = APIRouter(
    tags=["authentication"]
)

settings = get_settings()


def get_access_token(request: Request):
    """ Obtain Splitwise object (only if there is an access token """
    try:
        sObj = Splitwise(settings.CONSUMER_KEY, settings.CONSUMER_SECRET)
    except Exception as e:
        logger.error(f"Splitwise init failed: {e}")
        raise HTTPException(status_code=303, headers={"Location": "/login_sw"})

    token = request.session.get('access_token')
    if not token:
        raise HTTPException(status_code=303, headers={"Location": "/login_sw"})

    try:
        sObj.setOAuth2AccessToken(token)
        return sObj
    except Exception as e:
        logger.error(f"Failed to set access token: {e}")
        raise HTTPException(status_code=303, headers={"Location": "/login_sw"})

@router.get("/login_sw", name = "login_sw")
def login_sw(request: Request):
    sObj = Splitwise(settings.CONSUMER_KEY,  settings.CONSUMER_SECRET)
    url, state = sObj.getOAuth2AuthorizeURL(settings.BASE_URL + "/authorize")
    
    logger.info(f"State: {state}")
    request.session['state'] = state # Store state in session to double check later
    
    return RedirectResponse(url) #Redirect user to SW authorization website. After login, redirects user to the URL defined in the app's settings

@router.get("/authorize", name = "authorize", response_class = HTMLResponse)
def authorize(request: Request, code: str, state: str):
    """
    The user is redirected here after granting access to the app in Splitwise.
    
    Parameters:
    code (str): authorization code received from SW
    state (str): state that was sent in the initial request to SW
    
    Returns:
    HTMLResponse: redirects user to 'authorize_success.html'
    """
    
    # Get parameters needed to obtain the access token
    sObj = Splitwise(settings.CONSUMER_KEY, settings.CONSUMER_SECRET)
    
    state_previous = request.session.get('state')
    if state_previous != state:
        logger.warning(f"OAuth state mismatch — session: {state_previous!r}, incoming: {state!r}")
        raise HTTPException(status_code=400, detail="OAuth state mismatch")

    try:
        access_token = sObj.getOAuth2AccessToken(code, settings.BASE_URL + "/authorize") # Must be the same URL configured in Splitwise website for redirection! (https://secure.splitwise.com/apps/3979)
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return templates.TemplateResponse("authorize.html", {
            "request": request,
            "error": "Could not complete authorization. Please try again."
        })

    if not access_token:
        logger.error("getOAuth2AccessToken returned None (Splitwise responded with 'false')")
        return templates.TemplateResponse("authorize.html", {
            "request": request,
            "error": "Splitwise denied the authorization. Please try again."
        })

    sObj.setOAuth2AccessToken(access_token)
    
    # Store user data and tokens in session
    request.session['access_token'] = access_token
    current_user = sObj.getCurrentUser()
    request.session['user_id'] = current_user.id
    request.session['user_fname'] = current_user.first_name
    return templates.TemplateResponse("authorize_success.html", {"request": request})


@router.get("/logout", name = "logout")
def logout(request: Request):
    """
    Logout user by clearing the session and redirecting to the home page.
    
    Returns:
    RedirectResponse: redirects user to the home page
    """
    request.session.clear()
    return RedirectResponse("/")