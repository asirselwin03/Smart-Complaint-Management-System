from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
from collections import deque
import heapq

app = Flask(__name__)
app.secret_key = 'smart-college-demo-key'
DB = 'college.db'

REQUEST_WEIGHTS = {'Document': 40, 'Scholarship': 35, 'Academic': 30, 'Facilities': 20, 'IT': 15, 'Other': 10}
COMPLAINT_WEIGHTS = {'Anti-Ragging': 55, 'Harassment': 55, 'Grievance': 50, 'Discipline': 45, 'Academic': 35, 'Facilities': 25, 'IT': 20, 'Other': 20}
URGENCY_WEIGHTS = {'Critical': 60, 'High': 45, 'Medium': 30, 'Low': 15}

class PriorityQueue:
    def __init__(self): self.items = []
    def enqueue(self, item): heapq.heappush(self.items, (-item['priority'], item['created_at'], item['id'], item))
    def dequeue(self): return heapq.heappop(self.items)[-1] if self.items else None
    def peek(self): return self.items[0][-1] if self.items else None
    def is_empty(self): return not self.items
    def size(self): return len(self.items)

class Queue:
    def __init__(self): self.items = deque()
    def enqueue(self, item): self.items.append(item)
    def dequeue(self): return self.items.popleft() if self.items else None
    def peek(self): return self.items[0] if self.items else None
    def is_empty(self): return not self.items

class Stack:
    def __init__(self): self.items = []
    def push(self, item): self.items.append(item)
    def pop(self): return self.items.pop() if self.items else None
    def peek(self): return self.items[-1] if self.items else None
    def is_empty(self): return not self.items

def db():
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; return con

def init_db():
    con = db()
    con.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT UNIQUE,password TEXT,role TEXT);
    CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY AUTOINCREMENT,student_id INTEGER,kind TEXT,category TEXT,title TEXT,description TEXT,urgency TEXT,priority INTEGER,status TEXT,created_at INTEGER,created_text TEXT);
    CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,case_id INTEGER,status TEXT,note TEXT,created_text TEXT);''')
    if not con.execute("SELECT 1 FROM users WHERE email='student@college.com'").fetchone():
        con.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",('Demo Student','student@college.com','student123','student'))
    if not con.execute("SELECT 1 FROM users WHERE email='staff@college.com'").fetchone():
        con.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",('College Staff','staff@college.com','staff123','staff'))
    con.commit(); con.close()

def build_priority_queue(rows):
    pq = PriorityQueue()
    for r in rows: pq.enqueue(dict(r))
    result=[]
    while not pq.is_empty(): result.append(pq.dequeue())
    return result

def history_stack(case_id):
    con=db(); rows=con.execute('SELECT * FROM history WHERE case_id=? ORDER BY id',(case_id,)).fetchall(); con.close()
    st=Stack()
    for r in rows: st.push(dict(r))
    return st

@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        con=db(); u=con.execute('SELECT * FROM users WHERE email=? AND password=?',(request.form['email'],request.form['password'])).fetchone(); con.close()
        if u:
            session['user_id']=u['id']; session['role']=u['role']; session['name']=u['name']
            return redirect(url_for('staff_dashboard' if u['role']=='staff' else 'student_dashboard'))
        flash('Invalid email or password','error')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        try:
            con=db(); con.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',(request.form['name'],request.form['email'],request.form['password'],'student')); con.commit(); con.close()
            flash('Registration successful. Please login.','success'); return redirect(url_for('login'))
        except sqlite3.IntegrityError: flash('Email already registered.','error')
    return render_template('register.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

def score(kind, category, urgency):
    weight=(REQUEST_WEIGHTS if kind=='Request' else COMPLAINT_WEIGHTS).get(category,10)
    return weight + URGENCY_WEIGHTS.get(urgency,15)

@app.route('/student')
def student_dashboard():
    if session.get('role')!='student': return redirect(url_for('login'))
    con=db(); rows=con.execute('SELECT * FROM cases WHERE student_id=? ORDER BY id DESC',(session['user_id'],)).fetchall(); con.close()
    return render_template('student.html', cases=rows)

@app.route('/submit/<kind>', methods=['GET','POST'])
def submit(kind):
    if session.get('role')!='student': return redirect(url_for('login'))
    if kind not in ('Request','Complaint'): return redirect(url_for('student_dashboard'))
    categories=list((REQUEST_WEIGHTS if kind=='Request' else COMPLAINT_WEIGHTS).keys())
    if request.method=='POST':
        category=request.form['category']; urgency=request.form['urgency']; p=score(kind,category,urgency); now=int(datetime.now().timestamp()); text=datetime.now().strftime('%d-%m-%Y %I:%M %p')
        con=db(); cur=con.execute('INSERT INTO cases(student_id,kind,category,title,description,urgency,priority,status,created_at,created_text) VALUES(?,?,?,?,?,?,?,?,?,?)',(session['user_id'],kind,category,request.form['title'],request.form['description'],urgency,p,'Pending',now,text)); cid=cur.lastrowid; con.execute('INSERT INTO history(case_id,status,note,created_text) VALUES(?,?,?,?)',(cid,'Submitted','Case created and added to priority queue',text)); con.commit(); con.close()
        flash(f'{kind} submitted successfully. Priority score: {p}','success'); return redirect(url_for('student_dashboard'))
    return render_template('submit.html',kind=kind,categories=categories)

@app.route('/staff')
def staff_dashboard():
    if session.get('role')!='staff': return redirect(url_for('login'))
    con=db(); rows=con.execute('SELECT c.*,u.name student_name FROM cases c JOIN users u ON c.student_id=u.id ORDER BY c.id').fetchall(); con.close()
    pending=[r for r in rows if r['status']=='Pending']; pq=build_priority_queue(pending)
    return render_template('staff.html', cases=rows, queue=pq, next_case=(pq[0] if pq else None))

@app.route('/process/<int:cid>/<action>')
def process(cid,action):
    if session.get('role')!='staff': return redirect(url_for('login'))
    status='In Progress' if action=='start' else 'Resolved'
    con=db(); now=datetime.now().strftime('%d-%m-%Y %I:%M %p'); con.execute('UPDATE cases SET status=? WHERE id=?',(status,cid)); con.execute('INSERT INTO history(case_id,status,note,created_text) VALUES(?,?,?,?)',(cid,status,'Updated by staff',now)); con.commit(); con.close(); flash(f'Case #{cid} marked {status}.','success'); return redirect(url_for('staff_dashboard'))

@app.route('/history/<int:cid>')
def history(cid):
    if 'user_id' not in session: return redirect(url_for('login'))
    st=history_stack(cid); con=db(); case=con.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone(); con.close()
    return render_template('history.html',case=case,history=list(reversed(st.items)))

if __name__=='__main__':
    init_db(); app.run(debug=True)
