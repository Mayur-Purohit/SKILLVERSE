# Hosting on PythonAnywhere (SQLite Version)

This guide assumes you have a PythonAnywhere account (Free tier is fine for testing, but WebSocket/SocketIO features might not work perfectly on the free tier as they require persistent connections/workers which are limited).

## **Step 1: Prepare Your Files**

1.  **Zip your project folder**: Select all files in your `PROJECT D2` folder (app.py, templates, static, .env, requirements.txt, etc.) and create a ZIP file named `mysite.zip`.
    *   *Tip: Do NOT include `__pycache__` or `env`/`venv` folders to keep the upload small.*

## **Step 2: Upload to PythonAnywhere**

1.  Log in to [PythonAnywhere](https://www.pythonanywhere.com/).
2.  Go to the **Files** tab.
3.  Click **Upload a file** and upload your `mysite.zip`.
4.  Once uploaded, open a **Bash** console (from the Dashboard or Consoles tab).
5.  Run the following commands to unzip:
    ```bash
    unzip mysite.zip
    rm mysite.zip
    ```

## **Step 3: Install Dependencies**

1.  In the same **Bash** console, create a virtual environment:
    ```bash
    # Create virtualenv (assuming Python 3.10, adjust if needed)
    mkvirtualenv --python=/usr/bin/python3.10 myenv
    ```
    *You should see `(myenv)` appear at the start of your command prompt.*

2.  Install your requirements:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: If `psycopg2` fails (since we are on SQLite now), you can ignore it or remove it from `requirements.txt`.*

## **Step 4: Configure Web App**

1.  Go to the **Web** tab.
2.  Click **Add a new web app**.
3.  Click **Next**.
4.  Select **Manual configuration** (NOTE: Do NOT select "Flask" - manual gives you more control).
5.  Select **Python 3.10** (must match what you used in Step 3).
6.  Click **Next**.

## **Step 5: Set Paths**

On the Web tab dashboard:

1.  **Source code:** Enter `/home/yourusername/` (e.g., `/home/Manin/` if that's your username).
    *   *Check your Files tab to confirm the path. If you unzipped directly into home, it is just `/home/yourusername`.*
2.  **Working directory:** Same as above.
3.  **Virtualenv:** Enter the path to your virtualenv:
    ```
    /home/yourusername/.virtualenvs/myenv
    ```

## **Step 6: Configure WSGI File**

1.  On the Web tab, under "Code", find **WSGI configuration file** and click the link (something like `/var/www/yourusername_pythonanywhere_com_wsgi.py`).
2.  **Delete everything** in that file and paste this:

```python
import sys
import os
from dotenv import load_dotenv

# +++++++++++ DJANGO +++++++++++
# (Ignore Django section)

# +++++++++++ FLASK +++++++++++

# 1. Set the path to your project folder
project_folder = os.path.expanduser('~/')  # Adjust if you put files in a subfolder
if project_folder not in sys.path:
    sys.path.insert(0, project_folder)

# 2. Load environment variables from .env
load_dotenv(os.path.join(project_folder, '.env'))

# 3. Import flask app but need to wrap it for SocketIO if using it (Optional for simple hosting)
# Standard Flask import:
from app import app as application

# NOTE: PythonAnywhere Free Tier does NOT support WebSockets/SocketIO efficiently.
# Standard HTTP requests will work fine.
```

3.  Click **Save**.

## **Step 7: Reload & Visit**

1.  Go back to the **Web** tab.
2.  Click the big green **Reload** button at the top.
3.  Click the link to your site (e.g., `yourusername.pythonanywhere.com`).

---

## **Important Notes**

*   **SocketIO/Chat:** PythonAnywhere's **free tier** does not support `WebSocket` or `SocketIO` persistent connections well. Your real-time chat might fall back to "long-polling" (which is slower) or might not work reliably. You usually need a paid account for full WebSocket support.
*   **Database Path:** Since we use `sqlite:///StudyVerse.db`, it will look for the DB file in the current working directory. Since we set "Working directory" in Step 5, it should work fine.
*   **Static Files:** If CSS/JS is missing, go to the **Web** tab -> **Static files**:
    *   **URL:** `/static/`
    *   **Directory:** `/home/yourusername/static` (Use the full path to your static folder).
