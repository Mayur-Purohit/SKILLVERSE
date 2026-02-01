# 🚀 HOW TO UPLOAD & DEPLOY SKILLVERSE TO RENDER

This guide will walk you through deploying your **SkillVerse** project to the web using **Render** (free hosting).

---

## ✅ PREREQUISITES (Already Completed for You!)

I have already added the necessary files to your project:
1.  **`requirements.txt`**: Added `gunicorn` (Production Server).
2.  **`Procfile`**: Valid command to start the app (`web: gunicorn app:app`).

You are ready to upload!

---

## 📦 STEP 1: UPLOAD CODE TO GITHUB

Render pulls your code from GitHub. If you haven't uploaded your code yet:

1.  **Create a Repository** on GitHub (e.g., `skillverse-app`).
2.  **Upload your files**:
    *   Initialize git: `git init`
    *   Add files: `git add .`
    *   Commit: `git commit -m "Ready for deployment"`
    *   Push to GitHub:
        ```bash
        git remote add origin https://github.com/YOUR_USERNAME/skillverse-app.git
        git branch -M main
        git push -u origin main
        ```

*(If you don't know Git, you can simply **Drag & Drop** your project folder into the GitHub website upload page).*

---

## ☁️ STEP 2: CREATE WEB SERVICE ON RENDER

1.  **Go to [Render.com](https://render.com)** and Create a Free Account.
2.  Click **"New +"** button (top right) → Select **"Web Service"**.
3.  **Choose "Build and deploy from a Git repository"**.
4.  **Connect your GitHub account** (if asked) and select your `skillverse-app` repository.

---

## ⚙️ STEP 3: CONFIGURE SETTINGS

Fill in the details exactly as below:

| Setting | Value to Enter |
| :--- | :--- |
| **Name** | `skillverse` (or any name you like) |
| **Region** | `Oregon` or `Frankfurt` (choose closest to you) |
| **Branch** | `main` |
| **Root Directory** | `.` (Leave empty) |
| **Runtime** | **Python 3** |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |

---

## 🔑 STEP 4: ENVIRONMENT VARIABLES (Important!)

Scroll down to **"Eco System"** or **"Environment Variables"** section. click **"Add Environment Variable"**.

Add these keys and values (copy from your `.env` file):

| Key | Value |
| :--- | :--- |
| `FLASK_APP` | `app.py` |
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | `your_secret_key_here` (Use a strong random string) |
| `DATABASE_URL` | *See Step 5 below* |

---

## 🗄️ STEP 5: DATABASE SETUP (PostgreSQL)

Since Render's "Web Service" disks are ephemeral (files disappear on restart), you **CANNOT** use SQLite (`site.db`). You must use a **PostgreSQL** database.

**On Render Dashboard:**
1.  Click **"New +"** → Select **"PostgreSQL"**.
2.  **Name**: `skillverse-db`
3.  **Database**: `skillverse`
4.  **User**: `skillverse_user`
5.  **Region**: Same as your Web Service.
6.  **Plan**: Select **"Free"**.
7.  Click **"Create Database"**.

**Once created:**
1.  Look for **"Internal Database URL"**. Copy it.
2.  Go back to your **Web Service** → **Environment Variables**.
3.  Add/Update:
    *   Key: `DATABASE_URL`
    *   Value: `postgres://...` (Paste the Internal URL you copied)

---

## 🚀 STEP 6: DEPLOY!

1.  Click **"Create Web Service"** (button at the bottom).
2.  Render will start building your app. You will see logs scrolling.
3.  It may take 2-5 minutes.
4.  Once finished, you will see a green checkmark **"Live"**.
5.  Click the URL at the top (e.g., `https://skillverse.onrender.com`).

**🎉 Your website is now online!**

---

## 🛠️ TROUBLESHOOTING

- **"Internal Server Error"**: Check the "Logs" tab in Render to see the specific Python error.
- **Database Errors**: Ensure you copied the full `DATABASE_URL` correctly.
- **Missing Module**: Check if you forgot to add a library to `requirements.txt`.

---

**Mobile Access:**
Open `https://your-skillverse-app.onrender.com` on your phone. It works perfectly! 📱
