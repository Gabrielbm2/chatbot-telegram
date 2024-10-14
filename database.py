from pymongo import MongoClient, errors
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/bot_database")
client = MongoClient(MONGO_URI)
db = client['bot_database']
users_collection = db['users']
transactions_collection = db['transactions']

def update_balance(user_id, amount):
    user = get_user(user_id)
    if user:
        new_balance = user['balance'] + amount
        try:
            result = users_collection.update_one({"user_id": user_id}, {"$set": {"balance": new_balance}})
            if result.modified_count == 0:
                pass
        except errors.PyMongoError as e:
            pass
    else:
        pass

def get_user(user_id):
    try:
        user = users_collection.find_one({"user_id": user_id})
        return user
    except errors.PyMongoError as e:
        return None

def create_user_if_not_exists(user_id):
    try:
        if not users_collection.find_one({"user_id": user_id}):
            users_collection.insert_one({"user_id": user_id, "balance": 0, "state": {}})
        else:
            pass
    except errors.PyMongoError as e:
        pass

def update_user(user_id, user_data):
    update_data = {}
    for key, value in user_data.items():
        if key.startswith('$'):
            if key in update_data:
                update_data[key].update(value)
            else:
                update_data[key] = value
        else:
            if '$set' in update_data:
                update_data['$set'][key] = value
            else:
                update_data['$set'] = {key: value}

    try:
        result = users_collection.update_one({"user_id": user_id}, update_data)
        if result.modified_count == 0:
            pass
    except errors.PyMongoError as e:
        pass

def get_transactions(user_id):
    try:
        transactions = list(transactions_collection.find({"user_id": user_id}))
        return transactions
    except errors.PyMongoError as e:
        return []

def add_transaction(user_id, transaction_type, method, currency, amount):
    try:
        transactions_collection.insert_one({
            "user_id": user_id,
            "transaction_type": transaction_type,
            "method": method,
            "currency": currency,
            "amount": amount
        })
    except errors.PyMongoError as e:
        pass

def calculate_balance(user_id):
    transactions = get_transactions(user_id)
    balance = 0
    for transaction in transactions:
        if transaction["transaction_type"] == "deposit":
            balance += transaction["amount"]
        elif transaction["transaction_type"] == "withdrawal":
            balance -= transaction["amount"]
    return balance
