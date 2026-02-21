def fetch_user_birth_details(user_id: str) -> str:
    """
    Fetch birth details for an existing user from the MongoDB database.

    Use this tool when a user provides their user ID or when you need to
    check if a user's birth details already exist in the database.
    Call this tool at the start of every conversation to check if the
    user is new or returning.

    Args:
        user_id: The unique identifier of the user (UUID string).

    Returns:
        A JSON string with the user's birth details (name, date_of_birth,
        time_of_birth, place_of_birth) if found, or a not_found status
        if the user does not exist in the database.
    """
    import json
    import os
    from pymongo import MongoClient

    mongo_user = os.environ.get("MONGO_USER", "astrotalk")
    mongo_password = os.environ.get("MONGO_PASSWORD", "astrotalk123")
    mongo_host = os.environ.get("MONGO_HOST", "mongodb")
    mongo_port = os.environ.get("MONGO_PORT", "27017")
    mongo_db = os.environ.get("MONGO_DB", "astrotalk")

    uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}?authSource=admin"

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[mongo_db]
        collection = db["users"]

        user = collection.find_one(
            {"user_id": user_id},
            {
                "_id": 0,
                "name": 1,
                "date_of_birth": 1,
                "time_of_birth": 1,
                "place_of_birth": 1,
            },
        )

        if user:
            return json.dumps({"status": "found", "data": user})
        else:
            return json.dumps(
                {
                    "status": "not_found",
                    "message": f"No user found with user_id: {user_id}. This is a new user — please ask for their birth details.",
                }
            )
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        client.close()


def save_user_birth_details(
    user_id: str,
    name: str,
    date_of_birth: str,
    time_of_birth: str,
    place_of_birth: str,
) -> str:
    """
    Save birth details for a new user to the MongoDB database.

    Use this tool after collecting all four required birth details from
    a new user: their name, date of birth, time of birth, and place of
    birth. The user_id should be the same one from the conversation
    context (stored in the human memory block).

    Args:
        user_id: The unique identifier for this user (UUID string from the human memory block).
        name: The user's full name.
        date_of_birth: The user's date of birth (e.g. '1990-05-15' or '15 March 1990').
        time_of_birth: The user's time of birth (e.g. '14:30', '2:30 PM', or 'morning').
        place_of_birth: The user's place of birth (e.g. 'Mumbai, India').

    Returns:
        A JSON string confirming the save with the user_id, or an error message.
    """
    import json
    import os
    from datetime import datetime, timezone
    from pymongo import MongoClient

    mongo_user = os.environ.get("MONGO_USER", "astrotalk")
    mongo_password = os.environ.get("MONGO_PASSWORD", "astrotalk123")
    mongo_host = os.environ.get("MONGO_HOST", "mongodb")
    mongo_port = os.environ.get("MONGO_PORT", "27017")
    mongo_db = os.environ.get("MONGO_DB", "astrotalk")

    uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}?authSource=admin"

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[mongo_db]
        collection = db["users"]

        now = datetime.now(timezone.utc)

        doc = {
            "user_id": user_id,
            "name": name,
            "date_of_birth": date_of_birth,
            "time_of_birth": time_of_birth,
            "place_of_birth": place_of_birth,
            "created_at": now,
            "updated_at": now,
        }

        # Upsert: update if exists, insert if not
        collection.update_one(
            {"user_id": user_id},
            {"$set": doc},
            upsert=True,
        )

        return json.dumps(
            {
                "status": "saved",
                "user_id": user_id,
                "message": f"Birth details saved successfully for {name}.",
            }
        )
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        client.close()
