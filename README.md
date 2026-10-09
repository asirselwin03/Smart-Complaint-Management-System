# Smart College Complaint & Request Management System - Python Version

A college project using Python Flask, SQLite, Priority Queue, Queue/FIFO and Stack.

## Run on Windows
1. Install Python 3.11+.
2. Open PowerShell in this folder.
3. Run:
   `py -m venv venv`
   `venv\\Scripts\\activate`
   `pip install -r requirements.txt`
   `python app.py`
4. Open http://127.0.0.1:5000

## Demo accounts
Student: student@college.com / student123
Staff: staff@college.com / staff123

## Data structures
- PriorityQueue uses Python `heapq` and orders by priority descending, then submission time (FIFO for equal priority).
- Queue uses `collections.deque`.
- Stack uses a Python list for status history.
- SQLite stores users, cases and history.
