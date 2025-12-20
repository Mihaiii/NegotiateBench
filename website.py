from fasthtml.common import *
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app, rt = fast_app()


@rt("/")
def get():
    return Div(P("Hello World!"), hx_get="/change")


serve()
