from fastapi.templating import Jinja2Templates
from pathlib import Path

# Get the templates directory relative to the project root
TEMPLATES_DIR = Path("static/templates")

# Create a single instance of Jinja2Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))