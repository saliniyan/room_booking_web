# House_details.py
from pymongo import MongoClient

connection_string = "mongodb+srv://saliniyan:saliniyan@cluster0.tp4v7al.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def get_house_info():
    client = MongoClient(connection_string)
    db = client['mydatabase']
    collection = db['mycollection']

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

    client.close()
    return house_info
