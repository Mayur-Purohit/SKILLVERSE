from app import create_app, db
from models import Testimonial, User
from sqlalchemy import text
import random

app = create_app()

with app.app_context():
    # 1. Ensure Table Exists
    db.create_all()
    print("Database tables verified.")

    # 2. Add 'rating' column if it was missed in a previous migration manual step (safety check)
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE testimonials ADD COLUMN rating INTEGER DEFAULT 5"))
            conn.commit()
            print("Added rating column (if it was missing).")
    except Exception:
        pass # Column likely exists

    # 3. Seed 'Static' Testimonials PERMANENTLY into DB
    # These match the design from the image provided by user
    seed_data = [
        {
            "username": "SarahL",
            "full_name": "Sarah L",
            "role": "Student",
            "content": "The web design course provided a solid foundation for me. The instructors were knowledgeable and supportive, and the interactive learning environment was engaging. I highly recommend it!",
            "rating": 5,
            "avatar_bg": "ffc107"
        },
        {
            "username": "JasonM",
            "full_name": "Jason M",
            "role": "UI/UX Designer",
            "content": "The UI/UX design course exceeded my expectations. The instructor's expertise and practical assignments helped me improve my design skills. I feel more confident in my career now. Thank you!",
            "rating": 5,
            "avatar_bg": "198754"
        },
        {
            "username": "EmilyR",
            "full_name": "Emily R",
            "role": "App Developer",
            "content": "The mobile app development course was fantastic! The step-by-step tutorials and hands-on projects helped me grasp the concepts easily. I'm now building my own app. Great course!",
            "rating": 5,
            "avatar_bg": "0d6efd"
        },
        {
            "username": "MichaelK",
            "full_name": "Michael K",
            "role": "Graphic Designer",
            "content": "I enrolled in the graphic design course as a beginner, and it was the perfect starting point. The instructor's guidance and feedback improved my design abilities significantly. I'm grateful for this course!",
            "rating": 4,
            "avatar_bg": "6c757d"
        }
    ]

    for data in seed_data:
        # Check if identical content exists to prevent duplicates on multiple runs
        exists = Testimonial.query.filter_by(content=data['content']).first()
        if not exists:
            # Check/Create Dummy User
            user = User.query.filter_by(username=data['username']).first()
            if not user:
                user = User(
                    username=data['username'],
                    email=f"{data['username'].lower()}@example.com",
                    full_name=data['full_name'],
                    user_type='client',
                    password_hash='dummy_hash', 
                    avatar_url=None # Will use default generator in model
                )
                db.session.add(user)
                db.session.commit()
            
            # Create Testimonial
            t = Testimonial(
                user_id=user.id,
                content=data['content'],
                role=data['role'],
                rating=data['rating'],
                is_active=True
            )
            db.session.add(t)
            print(f"Seeded testimonial: {data['username']}")
    
    db.session.commit()
    print("Testimonials populated successfully.")
