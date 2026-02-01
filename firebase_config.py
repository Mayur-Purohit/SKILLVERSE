"""
Firebase Configuration and Initialization

This module sets up Firebase Admin SDK for Python Flask backend.
Provides Firestore database access and Firebase Authentication.

Author: SkillVerse Team
Purpose: Firebase integration for cloud database
"""

import firebase_admin
from firebase_admin import credentials, firestore, auth
import os

# Initialize Firebase Admin SDK
def initialize_firebase():
    """
    Initialize Firebase Admin SDK with service account credentials
    
    Returns:
        firestore.Client: Firestore database client
    """
    try:
        # Path to service account key JSON file
        # The file should be in the parent directory
        cred_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'studio-2531600845-cd0dd-firebase-adminsdk-fbsvc-f190dbbdb1.json'
        )
        
        # Check if file exists
        if not os.path.exists(cred_path):
            print(f"❌ Firebase credentials not found at: {cred_path}")
            return None
        
        # Initialize Firebase Admin
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        
        # Get Firestore client
        db = firestore.client()
        
        print("✓ Firebase initialized successfully!")
        return db
        
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        return None


# Firestore database client (global)
db = None


def get_db():
    """
    Get Firestore database client
    
    Returns:
        firestore.Client: Firestore database client
    """
    global db
    if db is None:
        db = initialize_firebase()
    return db


# Firebase Collections
class FirebaseCollections:
    """
    Firebase Firestore collection names
    
    This class defines all collection names used in Firestore
    """
    USERS = 'users'
    SERVICES = 'services'
    CATEGORIES = 'categories'
    REVIEWS = 'reviews'
    ORDERS = 'orders'
    FAVORITES = 'favorites'


# Helper functions for Firestore operations

def create_document(collection_name, data, doc_id=None):
    """
    Create a new document in Firestore
    
    Args:
        collection_name (str): Collection name
        data (dict): Document data
        doc_id (str): Optional document ID
        
    Returns:
        str: Document ID
    """
    db = get_db()
    if db is None:
        return None
    
    try:
        if doc_id:
            db.collection(collection_name).document(doc_id).set(data)
            return doc_id
        else:
            doc_ref = db.collection(collection_name).add(data)
            return doc_ref[1].id
    except Exception as e:
        print(f"Error creating document: {e}")
        return None


def get_document(collection_name, doc_id):
    """
    Get a document from Firestore
    
    Args:
        collection_name (str): Collection name
        doc_id (str): Document ID
        
    Returns:
        dict: Document data or None
    """
    db = get_db()
    if db is None:
        return None
    
    try:
        doc = db.collection(collection_name).document(doc_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        print(f"Error getting document: {e}")
        return None


def update_document(collection_name, doc_id, data):
    """
    Update a document in Firestore
    
    Args:
        collection_name (str): Collection name
        doc_id (str): Document ID
        data (dict): Updated data
        
    Returns:
        bool: Success status
    """
    db = get_db()
    if db is None:
        return False
    
    try:
        db.collection(collection_name).document(doc_id).update(data)
        return True
    except Exception as e:
        print(f"Error updating document: {e}")
        return False


def delete_document(collection_name, doc_id):
    """
    Delete a document from Firestore
    
    Args:
        collection_name (str): Collection name
        doc_id (str): Document ID
        
    Returns:
        bool: Success status
    """
    db = get_db()
    if db is None:
        return False
    
    try:
        db.collection(collection_name).document(doc_id).delete()
        return True
    except Exception as e:
        print(f"Error deleting document: {e}")
        return False


def query_collection(collection_name, filters=None, order_by=None, limit=None):
    """
    Query a collection in Firestore
    
    Args:
        collection_name (str): Collection name
        filters (list): List of tuples (field, operator, value)
        order_by (str): Field to order by
        limit (int): Maximum number of results
        
    Returns:
        list: List of documents
    """
    db = get_db()
    if db is None:
        return []
    
    try:
        query = db.collection(collection_name)
        
        # Apply filters
        if filters:
            for field, operator, value in filters:
                query = query.where(field, operator, value)
        
        # Apply ordering
        if order_by:
            query = query.order_by(order_by)
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        # Execute query
        docs = query.stream()
        
        # Convert to list of dicts
        results = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            results.append(data)
        
        return results
        
    except Exception as e:
        print(f"Error querying collection: {e}")
        return []


# Seed initial data to Firebase
def seed_firebase_data():
    """
    Seed initial categories and sample data to Firebase
    """
    db = get_db()
    if db is None:
        print("❌ Cannot seed data - Firebase not initialized")
        return
    
    print("Seeding Firebase data...")
    
    # Categories
    categories = [
        {
            'name': 'Web Development',
            'description': 'Website and web application development services',
            'icon': 'bi-code-slash',
            'color': 'bg-primary',
            'service_count': 0
        },
        {
            'name': 'Graphic Design',
            'description': 'Logo, branding, and graphic design services',
            'icon': 'bi-palette',
            'color': 'bg-danger',
            'service_count': 0
        },
        {
            'name': 'Content Writing',
            'description': 'SEO content, blog posts, and copywriting',
            'icon': 'bi-pen',
            'color': 'bg-warning',
            'service_count': 0
        },
        {
            'name': 'Video Editing',
            'description': 'Professional video editing and production',
            'icon': 'bi-camera-video',
            'color': 'bg-info',
            'service_count': 0
        },
        {
            'name': 'Tutoring',
            'description': 'Online tutoring and educational services',
            'icon': 'bi-book',
            'color': 'bg-success',
            'service_count': 0
        },
        {
            'name': 'Music & Audio',
            'description': 'Music production, mixing, and audio services',
            'icon': 'bi-music-note-beamed',
            'color': 'bg-secondary',
            'service_count': 0
        },
        {
            'name': 'Photography',
            'description': 'Professional photography services',
            'icon': 'bi-camera',
            'color': 'bg-dark',
            'service_count': 0
        },
        {
            'name': 'Marketing',
            'description': 'Digital marketing and social media services',
            'icon': 'bi-graph-up-arrow',
            'color': 'bg-primary',
            'service_count': 0
        }
    ]
    
    for category in categories:
        create_document(FirebaseCollections.CATEGORIES, category)
    
    print(f"✓ Seeded {len(categories)} categories to Firebase")


if __name__ == '__main__':
    """
    Test Firebase connection
    """
    print("Testing Firebase connection...")
    db = initialize_firebase()
    
    if db:
        print("✓ Firebase is ready!")
        
        # Seed data
        seed_firebase_data()
    else:
        print("❌ Firebase initialization failed")
