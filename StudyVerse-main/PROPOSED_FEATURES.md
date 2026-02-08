# 🚀 StudyVerse Feature Proposal: Semester 3 Edition

This document outlines 6 advanced productivity features for StudyVerse. These are designed to impress professors by demonstrating proficiency in **Algorithms, Database Management, AI Integration, and Real-Time Systems**.

---

## 1. AI Syllabus Scheduler (" The Strategist")
### 💡 The Concept
Instead of manual to-do lists, the user uploads a Syllabus PDF and sets a Deadline (e.g., "Exam on Friday"). The system automatically parses the content and generates a daily schedule derived from the deadline.

### ⚙️ Technical Implementation
*   **Input:** PDF File + Date Input.
*   **Logic (Algorithm):**
    1.  **Parsing:** Extract text from PDF (already existing logic).
    2.  **Segmentation:** AI identifies discrete chapters/topics.
    3.  **Scheduling Algorithm:** Calculate `Days_Remaining = Deadline - Today`. Divide `Total_Chapters / Days_Remaining`.
    4.  **Distribution:** Assign $N$ chapters to each day's date.
*   **Database:** Inserts rows into the `Todo` table with auto-calculated `due_date`.
*   **Stack:** Python (Pandas/Dateutil), PostgreSQL, Gemini AI.

---

## 2. Interactive Knowledge Heatmap ("The Analyst")
### 💡 The Concept
A visual grid showing the user's confidence in different topics. It moves beyond "Done/Not Done" to "Mastered/Struggling". Validates that the student is actually *learning*, not just ticking boxes.

### ⚙️ Technical Implementation
*   **Database:** Use the `TopicProficiency` table (`user_id`, `topic_name`, `score`).
*   **Data Collection:** After a study timer ends, a modal asks: "Rate your confidence (1-100)".
*   **Visualization Logic:**
    *   Backend sends a JSON list of topics + scores.
    *   Frontend (JS) maps scores to logical colors: Reading (0-30% Red), Reviewing (31-70% Yellow), Mastered (71-100% Green).
*   **Stack:** JavaScript (Canvas or Div Grid), PostgreSQL.

---

## 3. Zen Mode + Distraction Handling ("The Zone")
### 💡 The Concept
A "hardcore" focus mode that minimizes the UI and manages psychological distractions. It acknowledges that brains wander and provides a tool to handle it.

### ⚙️ Technical Implementation
*   **State Management:** CSS Toggle class `.zen-active` on the `<body>` (hides Nav, Chat, Friends).
*   **Browser Storage:** The "Distraction Pad" (a notepad for intrusive thoughts) saves to `localStorage`. It does **not** hit the server database to save bandwidth/latency.
*   **Audio API:** Uses the Web Audio API to play non-looping white noise or binaural beats entirely on the client side.
*   **Stack:** Advanced CSS3, LocalStorage API, HTML5 Audio.

---

## 4. AI "Weakness" Quiz Generator
### 💡 The Concept
Since you removed standard Flashcards, this is the upgrade. The AI looks at the `TopicProficiency` table, finds topics with **Low Scores**, and generates a unique encoded 5-question quiz just for those weak areas.

### ⚙️ Technical Implementation
*   **Algorithm:** Query `TopicProficiency WHERE score < 40`. Select random topic.
*   **Generation:** Send topic context to Gemini AI: *"Create 5 Multiple Choice Questions for [Topic] in JSON format"*.
*   **Validation:** Compare user clicks to the JSON numeric answer key.
*   **Feedback Loop:** If user passes ($>80\%$), update `TopicProficiency` score in DB automatically.
*   **Stack:** Gemini AI, JSON parsing, AJAX.

---

## 5. Real-Time Collaborative Whiteboard
### 💡 The Concept
Students learn better together. A shared canvas where two friends can draw diagrams or solve math problems simultaneously.

### ⚙️ Technical Implementation
*   **Networking:** Uses `Socket.io` (WebSockets) for bi-directional real-time communication.
*   **Canvas API:** HTML5 `<canvas>` element tracks mouse coordinates `(x, y)`.
*   **Broadcasting:** When User A draws a line, `socket.emit('draw', {x, y})` is sent. Server broadcasts this to User B, and User B's browser draws the line instantly.
*   **Stack:** Flask-SocketIO, HTML5 Canvas.

---

## 6. Smart Study-Buddy Matchmaking
### 💡 The Concept
An algorithm that pairs users based on **compatibility** rather than just random lists.

### ⚙️ Technical Implementation
*   **The Algorithm:**
    *   Compare `User A` and `User B`.
    *   **Score Calculation:**
        *   Same Focus Goals/Tags (+10 points)
        *   Similar Active Hours (+5 points)
        *   Similar Level range (+5 points)
    *   Return a list of users with `Compatibility_Score > 70%`.
*   **Database:** Complex SQL Query or Python filtering logic.
*   **Stack:** Python Logic, PostgreSQL advanced querying.
