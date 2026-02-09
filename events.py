"""
Socket.IO Event Handlers for Real-Time Chat

This module handles WebSocket events for real-time messaging
"""

from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room
from models import db, Message, Order, Notification
from managers import chat_manager
import pytz
from datetime import datetime

# Global set to track online users (simple in-memory storage)
# NOTE: In a multi-worker environment without Redis, this set is local to each worker.
# However, since we are using Gunicorn with 1 worker (gevent), this works fine.
online_users = set()

def register_socketio_events(socketio):
    """Register all socket.io event handlers"""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        if current_user.is_authenticated:
            online_users.add(current_user.id)
            print(f'[Socket] User {current_user.username} ({current_user.id}) connected. SID: {request.sid}')
            # Broadcast user online status
            emit('user_status', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)
        
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        if current_user.is_authenticated:
            if current_user.id in online_users:
                online_users.remove(current_user.id)
            print(f'[Socket] User {current_user.username} ({current_user.id}) disconnected. SID: {request.sid}')
            # Broadcast user offline status
            emit('user_status', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

    @socketio.on('check_users_status')
    def handle_check_status(data):
        """Check status for a list of user IDs"""
        user_ids = data.get('user_ids', [])
        status_map = {}
        for uid in user_ids:
            try:
                uid = int(uid)
                status_map[uid] = 'online' if uid in online_users else 'offline'
            except (ValueError, TypeError):
                continue
        
        emit('users_status_response', status_map)
    
    @socketio.on('join')
    def handle_join(data):
        """Join a chat room (order-based)"""
        if not current_user.is_authenticated:
            return
        
        order_id = data.get('order_id')
        if not order_id:
            return
        
        # Verify user is part of this order
        order = Order.query.get(order_id)
        if not order:
            return
            
        if current_user.id not in [order.buyer_id, order.seller_id]:
            return
        
        room = f'order_{order_id}'
        join_room(room)
        
        print(f'[Socket] User {current_user.username} joined room {room}')
        
        # Notify others in the room
        emit('joined', {
            'user_id': current_user.id,
            'username': current_user.username
        }, room=room)
    
    @socketio.on('leave')
    def handle_leave(data):
        """Leave a chat room"""
        if not current_user.is_authenticated:
            return
        
        order_id = data.get('order_id')
        if not order_id:
            return
        
        room = f'order_{order_id}'
        leave_room(room)
        print(f'[Socket] User {current_user.username} left room {room}')
    
    @socketio.on('send_message')
    def handle_send_message(data):
        """Handle incoming chat message"""
        if not current_user.is_authenticated:
            return
        
        order_id = data.get('order_id')
        content = data.get('content')
        temp_id = data.get('temp_id')  # For optimistic UI matching
        
        if not order_id or not content:
            return
        
        # 1. Save message to database
        message, error = chat_manager.send_message(order_id, current_user.id, content)
        
        if error:
            emit('error', {'message': error})
            return
        
        # 2. Prepare Message Data (IST Time)
        ist_tz = pytz.timezone('Asia/Kolkata')
        created_at = message.created_at
        if created_at.tzinfo is None:
            utc_tz = pytz.UTC
            created_at = utc_tz.localize(created_at)
        ist_time = created_at.astimezone(ist_tz)
        
        message_payload = {
            'id': message.id,
            'temp_id': temp_id,
            'order_id': order_id,
            'sender_id': message.sender_id,
            'sender_name': current_user.username,
            'content': message.content,
            'created_at': ist_time.isoformat(),
            'time_display': ist_time.strftime('%I:%M %p')
        }
        
        # 3. CRITICAL FIX: Broadcast to Room with broadcast=True
        # This ensures EVERYONE in the room receives it, including the sender
        # This matches the working StudyVerse implementation
        room = f'order_{order_id}'
        print(f'📤 [Socket] Broadcasting message to room {room}: {content[:50]if len(content)>50 else content}')
        emit('new_message', message_payload, room=room, broadcast=True)
        print(f'✅ [Socket] Message broadcasted successfully')

        # 4. Handle Notifications (Async check)
        try:
            order = Order.query.get(order_id)
            if order:
                recipient_id = order.seller_id if current_user.id == order.buyer_id else order.buyer_id
                
                # Check if recipient is active in the room (optional optimization)
                # For now, we simple create a notification if they haven't seen it recently
                
                # Notification logic
                notification = Notification(
                    user_id=recipient_id,
                    title=f'New Message from {current_user.username}',
                    message=f'{current_user.username}: {content[:30]}...',
                    link=f'/user/order/{order_id}' # Fixed URL path
                )
                db.session.add(notification)
                db.session.commit()
        except Exception as e:
            print(f"[Socket Error] Notification failed: {e}")

