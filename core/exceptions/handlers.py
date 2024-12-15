from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="static/templates")

def apology(message, request, code=400):
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
    return templates.TemplateResponse("apology.html", {"request": request, "top" : code, "bottom" : escape(message)}, status_code=code)
