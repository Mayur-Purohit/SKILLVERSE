"""
Email Service Module for StudyVerse
Handles all email functionality including welcome emails for new users.
"""

from flask_mail import Mail, Message
from flask import render_template
import os
from threading import Thread

# Mail instance (will be initialized in app.py)
mail = Mail()

def init_mail(app):
    """Initialize Flask-Mail with app configuration."""
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    # Keep the fix for spaces in password as it is robust
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '').replace(' ', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 
                                                        f"StudyVerse <{os.environ.get('MAIL_USERNAME')}>")
    mail.init_app(app)
    return mail

def send_async_email(app, msg):
    """Send email asynchronously in a background thread."""
    with app.app_context():
        try:
            mail.send(msg)
            print(f"✓ Email sent successfully to {msg.recipients}")
        except Exception as e:
            print(f"✗ Failed to send email: {str(e)}")

def send_email(subject, recipients, html_body, text_body=None):
    """
    Send an email with HTML and optional text body.
    
    Args:
        subject (str): Email subject
        recipients (list): List of recipient email addresses
        html_body (str): HTML content of the email
        text_body (str, optional): Plain text version of the email
    
    Returns:
        bool: True if email was queued successfully, False otherwise
    """
    from flask import current_app
    
    try:
        msg = Message(
            subject=subject,
            recipients=recipients if isinstance(recipients, list) else [recipients],
            html=html_body,
            body=text_body or "Please view this email in an HTML-compatible client."
        )
        
        # Send email asynchronously to avoid blocking
        Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
        return True
    except Exception as e:
        print(f"✗ Error preparing email: {str(e)}")
        return False

def send_welcome_email(user_email, user_first_name, user_last_name=""):
    """
    Send a welcome email to a new user.
    
    Args:
        user_email (str): User's email address
        user_first_name (str): User's first name
        user_last_name (str, optional): User's last name
    
    Returns:
        bool: True if email was queued successfully, False otherwise
    """
    try:
        full_name = f"{user_first_name} {user_last_name}".strip() or "Student"
        
        # Render HTML template
        html_body = render_template(
            'email/welcome.html',
            first_name=user_first_name or "Student",
            full_name=full_name
        )
        
        # Plain text fallback
        text_body = f"""
Welcome to StudyVerse, {full_name}!

We're excited to have you join us on your learning journey.

StudyVerse is your intelligent study companion, designed to help you:
• Master your subjects with AI-powered coaching
• Stay organized with smart task management
• Collaborate effectively with study groups
• Track your progress and build momentum

Get started now and take control of your academic success!

Best regards,
The StudyVerse Team
        """.strip()
        
        return send_email(
            subject=f"Welcome to StudyVerse, {user_first_name}! 🚀",
            recipients=user_email,
            html_body=html_body,
            text_body=text_body
        )
    except Exception as e:
        print(f"✗ Error sending welcome email: {str(e)}")
        return False

def send_task_reminder_email(user_email, user_first_name, task_title, due_date, due_time):
    """
    Send an email reminder for a due task.
    """
    try:
        
        # Simple HTML body
        html_body = f"""
        <h2>Hello {user_first_name},</h2>
        <p>This is a reminder for your task:</p>
        <p><strong>{task_title}</strong></p>
        <p>Due: {due_date} {due_time if due_time else ''}</p>
        <p>Don't forget to complete it!</p>
        <br>
        <p>Best regards,</p>
        <p>StudyVerse Team</p>
        """
        
        text_body = f"Reminder: Task '{task_title}' is due on {due_date} {due_time or ''}."

        return send_email(
            subject=f"Reminder: {task_title} is due soon! ⏰",
            recipients=user_email,
            html_body=html_body,
            text_body=text_body
        )
    except Exception as e:
        print(f"✗ Error sending task reminder email: {str(e)}")
        return False
