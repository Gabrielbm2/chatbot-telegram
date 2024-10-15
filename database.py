from pymongo import MongoClient, errors
import os
import time

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27016/bot_database")
client = MongoClient(MONGO_URI)
db = client['bot_database']
users_collection = db['users']
transactions_collection = db['transactions']


def update_balance(user_id):
    new_balance = calculate_balance(user_id)
    try:
        users_collection.update_one({"user_id": user_id}, {"$set": {"balance": new_balance}})
    except errors.PyMongoError as e:
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
        users_collection.update_one({"user_id": user_id}, update_data)
    except errors.PyMongoError as e:
        pass


def get_transactions(user_id):
    try:
        transactions = list(transactions_collection.find({"user_id": user_id}))
        return transactions
    except errors.PyMongoError as e:
        return []


def add_transaction(user_id, transaction_type, method, currency, amount):
    if not transaction_type or not method or not currency or amount is None:
        raise ValueError("All transaction details must be provided")

    transaction = {
        "user_id": user_id,
        "transaction_type": transaction_type,
        "method": method,
        "currency": currency,
        "amount": amount,
        "timestamp": time.time()
    }

    try:
        transactions_collection.insert_one(transaction)
        update_balance(user_id)
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


def update_all_balances():
    users = users_collection.find()
    for user in users:
        user_id = user['user_id']
        new_balance = calculate_balance(user_id)
        try:
            users_collection.update_one({"user_id": user_id}, {"$set": {"balance": new_balance}})
        except errors.PyMongoError as e:
            pass
