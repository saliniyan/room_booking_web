from flask import Flask, render_template, request, g, redirect, url_for, session, flash
import pandas as pd
from House_details import get_house_info
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
from config import connection_string

application = Flask(__name__)
application.secret_key = "hello"


try:
    client = MongoClient(connection_string)
    db = client['Room_booking']
    reservations = db['reservations']
    collection = db['Rooms']
    users= db['users']
except Exception as e:
    print("Error in connection",e)

house_info = get_house_info()
data_dict = {}

def load_user_data():
    global data_dict
    data_dict = {}
    documents = users.find()
    for doc in documents:
        doc['_id'] = str(doc['_id'])
        data_dict[doc['username']] = doc['password']

load_user_data() #called initailly

@application.route('/')
def index():
    return render_template('login.html')

@application.route('/authenticate', methods=['POST'])
def authenticate():
    username = request.form['username']
    password = request.form['password']

    if username in data_dict and data_dict[username] == password:
        session['username'] = username
        return redirect(url_for('index1'))  # Redirect to index1 route
    elif username == 'b' and password == '456':
        session['username'] = username
        return redirect(url_for('admin_panel'))  # Redirect to admin_panel route
    else:
        return "Invalid credentials"

@application.route('/index1')
def index1():
    if 'username' in session and session['username'] in data_dict:
        return render_template('index1.html')
    else:
        return redirect(url_for('index'))

@application.route('/submit', methods=['POST'])
def submit():
    check_in = request.form['check_in']
    check_out = request.form['check_out']
    rooms_needed = int(request.form['rooms'])

    if not check_in or not check_out or rooms_needed <= 0:
        return "Invalid input. Please fill in all fields correctly."
    
    available_houses = []
    for house_id, info in house_info.items():
        try:
            if int(info['rooms']) >= int(rooms_needed):
                available_houses.append(house_id)
        except ValueError:
            print(f"Invalid data for house {house_id}: rooms={info['rooms']} or rooms_needed={rooms_needed}")

    available_results = []
    for house_id in available_houses:
        booking_count = reservations.count_documents({
            "House_NO": house_id,
            "$or": [
                {"check_in": {"$gte": check_in, "$lte": check_out}},
                {"check_out": {"$gte": check_in, "$lte": check_out}}
            ],
            "status": {"$ne": "rejected"}
        })
        if booking_count == 0:
            house_description = house_info[house_id]['description']
            house_url = house_info[house_id]['url']
            available_results.append({
                'house_id': house_id,
                'rooms': house_info[house_id]['rooms'],
                'description': house_description,
                'url': house_url
            })

    if available_results:
        return render_template('available_houses.html', available_results=available_results)
    else:
        return "Sorry, no houses are available for your requested dates or rooms."

@application.route('/book', methods=['POST'])
def book():
    house_id = request.form['house_id']
    check_in = request.form['check_in']
    check_out = request.form['check_out']

    if not house_id or not check_in or not check_out:
        return "Invalid input. Please fill in all fields correctly."

    # Render the guest details form, passing house booking details as parameters
    return render_template('guest_details_form.html', house_id=house_id, check_in=check_in, check_out=check_out)

@application.route('/submit_form', methods=['POST'])
def submit_form():
    form_data = {
        "name": request.form['name'],
        "designation": request.form['designation'],
        "phone_no": request.form['phone_no'],
        "purpose_of_visit": request.form['purpose_of_visit'],
        "originator_name": request.form['originator_name'],
        "department_contact_no": request.form['department_contact_no'],
        "no_of_breakfast": request.form['no_of_breakfast'],
        "no_of_lunch": request.form['no_of_lunch'],
        "no_of_dinner": request.form['no_of_dinner'],
        "House_NO": request.form['house_id'],
        "check_in": request.form['check_in'],
        "check_out": request.form['check_out'],
        "status": "pending"
    }

    reservations.insert_one(form_data)
    success_message = "Your request is successfully sent to admin"
    return render_template('success.html', success_message=success_message)

@application.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'username' not in session or session['username'] != 'b':
        return redirect(url_for('index'))

    if request.method == 'GET':
        pending_bookings = list(reservations.find({"status": "pending"}))
        return render_template('admin_panel.html', pending_bookings=pending_bookings)

    elif request.method == 'POST':
        # Get form data
        action = request.form.get('action')  # Action can be 'accept' or 'reject'
        reason = request.form.get('reason', '')  # Reason for rejection (if any)
        house_no = request.form.get('House_NO')  # The House_NO from the form

        # Determine the status based on the action
        status = 'accepted' if action == 'accept' else 'rejected'

        # Update the reservation for the specific house_no
        result = reservations.update_one(
            {"House_NO": house_no, "status": "pending"},  # Match by House_NO and status
            {"$set": {"status": status, "reason": reason}}  # Update only the matched booking
        )

        # Check if the update was successful
        if result.matched_count == 0:
            flash("No pending booking found with the provided house ID.")
        else:
            flash("Booking status updated successfully.")

        return redirect(url_for('admin_panel'))

            
@application.route('/accepted_bookings', methods=['GET'])
def database_view():
    accepted_bookings = db.reservations.find({'status': 'accepted'})
    accepted_bookings_list = list(accepted_bookings)
    df = pd.DataFrame(accepted_bookings_list)
    return render_template('accepted_bookings.html', bookings=df.to_dict(orient='records'))

@application.route('/add_rooms', methods=['GET', 'POST'])
def add_rooms():
    if request.method == 'POST':
        # Get data from the form
        rooms = request.form['rooms']
        adults = request.form['adults']
        children = request.form['children']
        description = request.form['description']
        url = request.form['url']
        
        # Create a document to insert into MongoDB
        room_data = {
            'rooms': rooms,
            'adults': int(adults),
            'children': int(children),
            'description': description,
            'url': url
        }
        
        # Insert the data into the collection
        collection.insert_one(room_data)

        global house_info
        house_info = get_house_info()

        # Redirect to a confirmation page or back to the form
        return redirect(url_for('admin_panel'))

    return render_template('add_rooms.html')

@application.route('/view_rooms')
def view_rooms():
    house_info = {}
    documents = collection.find()
    
    for doc in documents:
        house_info[str(doc['_id'])] = {
            'rooms': doc.get('rooms'),
            'adults': doc.get('adults'),
            'children': doc.get('children'),
            'description': doc.get('description'),
            'url': doc.get('url')
        }
    
    return render_template('view_rooms.html', house_info=house_info)


@application.route('/delete_room/<house_id>', methods=['POST'])
def delete_room(house_id):
    if not house_id or len(house_id) != 24:
        print("Invalid house_id provided.")
        return redirect('/view_rooms')
    
    try:
        collection.delete_one({'_id': ObjectId(house_id)})  # Using ObjectId
        global house_info
        house_info = get_house_info()
        return redirect('/view_rooms')
    except InvalidId:
        print("Invalid ObjectId format.")
        return redirect('/view_rooms')
    except Exception as e:
        print(f"Error deleting room: {e}")
        return redirect('/view_rooms')

@application.route('/add_user', methods=['GET'])
def add_user():
    return render_template('add_user.html')

@application.route('/add_user', methods=['POST'])
def register():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']

    # Check if the username or email already exists
    existing_user = users.find_one({'$or': [{'username': username}, {'email': email}]})
    if existing_user:
        flash('Username or email already exists. Please choose a different one.', 'danger')
        return redirect(url_for('add_user'))
    new_user = {
        'username': username,
        'email': email,
        'password': password
    }

    users.insert_one(new_user)
    flash('User registered successfully!', 'success')
    
    return redirect(url_for('add_user'))

if __name__ == '__main__':
    application.run(debug=True)