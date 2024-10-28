# House_details.py

from pymongo import MongoClient
from bson.objectid import ObjectId
from config import connection_string

def get_house_info():
    house_info = {}
    
    try:
        # Connect to MongoDB
        client = MongoClient(connection_string)
        db = client['Room_booking']
        collection = db['Rooms']
        
        # Retrieve all documents in the Rooms collection
        documents = collection.find()
        
        # Populate house_info with room details
        for doc in documents:
            house_id = str(doc['_id'])  # Convert ObjectId to string for easier handling in Flask
            house_info[house_id] = {
                'rooms': doc.get('rooms', 0),
                'adults': doc.get('adults', 0),
                'children': doc.get('children', 0),
                'description': doc.get('description', ''),
                'url': doc.get('url', '')
            }
    
    except Exception as e:
        print("Error fetching house info:", e)
    
    return house_info
