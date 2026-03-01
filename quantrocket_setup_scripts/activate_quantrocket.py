from quantrocket.license import set_license
from dotenv import load_dotenv
import os

load_dotenv()

set_license(os.getenv("LICENSE_KEY"))