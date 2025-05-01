from pymongo import MongoClient
from pymongo.errors import CollectionInvalid, OperationFailure
import os
from dotenv import load_dotenv

# Load environment variables for configuration
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "lip-c")

# Create a global client instance
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]


def init_db():
    """
    Apply JSON Schema validators to all collections. If a collection already exists,
    modify it to enforce the schema. If it doesn't, create it with validation.
    """
    validators = {
        "users": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["username", "password_hash", "name", "contacts"],
                "properties": {
                    "username": {"bsonType": "string", "description": "must be a string and is required"},
                    "password_hash": {"bsonType": "string", "description": "must be a string and is required"},
                    "name": {"bsonType": "string", "description": "must be a string and is required"},
                    "profile_pic": {"bsonType": "string", "description": "must be a string"},
                    "contacts": {
                        "bsonType": "array",
                        "items": {"bsonType": "objectId"},
                        "description": "must be an array of ObjectId references"
                    }
                }
            }
        },
        "calls": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["caller_id", "callee_id", "started_at", "ended_at", "duration_seconds", "transcripts"],
                "properties": {
                    "caller_id": {"bsonType": "objectId", "description": "must be an ObjectId and is required"},
                    "callee_id": {"bsonType": "objectId", "description": "must be an ObjectId and is required"},
                    "started_at": {"bsonType": "date", "description": "must be a date and is required"},
                    "ended_at": {"bsonType": "date", "description": "must be a date and is required"},
                    "duration_seconds": {"bsonType": ["double", "int"], "description": "must be a number and is required"},
                    "transcripts": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "required": ["t", "speaker", "text", "source"],
                            "properties": {
                                "t": {"bsonType": "date", "description": "timestamp of transcript line"},
                                "speaker": {"bsonType": "objectId", "description": "ObjectId of the speaker"},
                                "text": {"bsonType": "string", "description": "transcribed text"},
                                "source": {"bsonType": "string", "description": "source of transcription (e.g., lip, vosk)"}
                            }
                        },
                        "description": "array of transcript objects"
                    }
                }
            }
        },
        "refresh_tokens": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["user_id", "jti", "token_hash", "expires_at", "revoked", "created_at"],
                "properties": {
                    "user_id": {"bsonType": "objectId", "description": "must be an ObjectId referencing a user"},
                    "jti": {"bsonType": "string", "description": "JWT ID string"},
                    "token_hash": {"bsonType": "string", "description": "hash of the token"},
                    "expires_at": {"bsonType": "date", "description": "expiration date of the token"},
                    "revoked": {"bsonType": "bool", "description": "revocation status"},
                    "created_at": {"bsonType": "date", "description": "creation timestamp"},
                    "replaced_by_jti": {"bsonType": "string", "description": "JTI of replacement token"},
                    "revoked_at": {"bsonType": "date", "description": "revocation timestamp"}
                }
            }
        }
    }

    for name, schema in validators.items():
        try:
            # Try creating with validator if collection doesn't exist
            db.create_collection(
                name,
                validator=schema,
                validationLevel="strict",
                validationAction="error"
            )
            print(f"Created collection '{name}' with schema validation.")
        except CollectionInvalid:
            # If it exists, attempt to modify the collection to apply the schema
            try:
                db.command(
                    {
                        "collMod": name,
                        "validator": schema,
                        "validationLevel": "strict",
                        "validationAction": "error"
                    }
                )
                print(
                    f"Updated schema validation for existing collection '{name}'.")
            except OperationFailure as e:
                # Insufficient privileges or other failure => skip
                print(f"Skipping schema update for '{name}': {e}")


def get_collection(collection_name):
    """
    Retrieve a collection by name.
    """
    return db[collection_name]


# Initialize validators on module load
init_db()
