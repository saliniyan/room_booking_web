from flask import Flask, render_template, request, g, redirect, url_for, flash, make_response, session
from pymongo import MongoClient
from bson.objectid import ObjectId
from config import connection_string, JWT_SECRET
import bcrypt
import jwt
from functools import wraps
from datetime import datetime, timedelta
import pandas as pd
from House_details import get_house_info

application = Flask(__name__)
application.secret_key = "hello"

JWT_ALGORITHM = "HS256"
JWT_EXP_SECONDS = 3600

#  MongoDB
client = MongoClient(connection_string)
db = client['Room_booking']
reservations = db['reservations']
collection = db['Rooms']
users = db['users']

# Load houses
house_info = get_house_info()


# JWT Helpers 
def create_token(user):
    payload = {
        "user_id": str(user["_id"]),
        "username": user["username"],
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(seconds=JWT_EXP_SECONDS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get("access_token")
        if not token:
            return redirect(url_for("index"))

        try:
            g.user = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except:
            return redirect(url_for("index"))

        return f(*args, **kwargs)
    return wrapper


# Admin (NO JWT)
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper


#  ROUTES
@application.route('/')
def index():
    return render_template('login.html')


#  Add User (Admin only)
@application.route('/add_user', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'GET':
        return render_template('add_user.html')

    username = request.form['username']
    email = request.form['email']
    password = request.form['password']

    if users.find_one({"username": username}):
        flash("Username already exists", "danger")
        return redirect(url_for("add_user"))

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    users.insert_one({
        "username": username,
        "email": email,
        "password": hashed,
        "role": "user"
    })

    flash("User created successfully!", "success")
    return redirect(url_for("admin_panel"))


#  Login 
@application.route('/authenticate', methods=['POST'])
def authenticate():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        flash("Enter username & password", "danger")
        return redirect(url_for('index'))

    # Admin login (NO JWT)
    if username == "b" and password == "123":
        session["is_admin"] = True
        resp = make_response(redirect(url_for('admin_panel')))
        resp.delete_cookie("access_token")
        return resp

    # Normal user
    user = users.find_one({"username": username})
    if not user:
        flash("Invalid username or password", "danger")
        return redirect(url_for("index"))

    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        flash("Invalid username or password", "danger")
        return redirect(url_for("index"))

    token = create_token(user)
    resp = make_response(redirect(url_for('index1')))

    resp.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="Lax"   # Works on localhost
    )

    return resp


#  Logout 
@application.route('/logout')
def logout():
    session.clear()
    resp = make_response(redirect(url_for("index")))
    resp.delete_cookie("access_token")
    return resp


#  User Dashboard 
@application.route('/index1')
@token_required
def index1():
    return render_template('index1.html')


#  Submit Search 
@application.route('/submit', methods=['POST'])
@token_required
def submit():
    check_in = request.form['check_in']
    check_out = request.form['check_out']
    rooms_needed = int(request.form['rooms'])

    available = []
    for hid, info in house_info.items():
        if int(info['rooms']) >= rooms_needed:
            count = reservations.count_documents({
                "House_NO": hid,
                "$and": [
                    {"check_in": {"$lte": check_out}},
                    {"check_out": {"$gte": check_in}}
                ],
                "status": {"$ne": "rejected"}
            })
            if count == 0:
                available.append({
                    "house_id": hid,
                    "rooms": info['rooms'],
                    "description": info['description'],
                    "url": info['url']
                })

    return render_template("available_houses.html", available_results=available)


#  Book 
@application.route('/book', methods=['POST'])
@token_required
def book():
    return render_template(
        "guest_details_form.html",
        house_id=request.form['house_id'],
        check_in=request.form['check_in'],
        check_out=request.form['check_out']
    )


#  Submit Form 
@application.route('/submit_form', methods=['POST'])
@token_required
def submit_form():
    form_data = dict(request.form)
    form_data["status"] = "pending"
    form_data["requested_by"] = g.user["username"]

    reservations.insert_one(form_data)
    return render_template("success.html", success_message="Request submitted!")


#  Admin Panel 
@application.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin_panel():
    if request.method == 'GET':
        pending = list(reservations.find({"status": "pending"}))
        return render_template("admin_panel.html", pending_bookings=pending)

    action = request.form['action']
    house_no = request.form['House_NO']
    reason = request.form.get('reason', '')

    status = "accepted" if action == "accept" else "rejected"
    reservations.update_one(
        {"House_NO": house_no, "status": "pending"},
        {"$set": {"status": status, "reason": reason}}
    )
    return redirect(url_for("admin_panel"))


#  Accepted Bookings 
@application.route('/accepted_bookings')
@admin_required
def accepted_bookings():
    data = list(reservations.find({"status": "accepted"}))
    df = pd.DataFrame(data)
    return render_template("accepted_bookings.html", bookings=df.to_dict(orient="records"))


#  Add Rooms 
@application.route('/add_rooms', methods=['GET', 'POST'])
@admin_required
def add_rooms():
    if request.method == 'POST':
        collection.insert_one(dict(request.form))
        return redirect(url_for("admin_panel"))
    return render_template("add_rooms.html")


#  View Rooms 
@application.route('/view_rooms')
@admin_required
def view_rooms():
    rooms = {str(doc["_id"]): doc for doc in collection.find()}
    return render_template("view_rooms.html", house_info=rooms)


#  Delete Room 
@application.route('/delete_room/<id>', methods=['POST'])
@admin_required
def delete_room(id):
    try:
        collection.delete_one({"_id": ObjectId(id)})
    except:
        pass
    return redirect(url_for("view_rooms"))


#  Run 
if __name__ == '__main__':
    application.run(debug=True)
