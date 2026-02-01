"""
Standalone script to credit seller for Order #64
Uses PostgreSQL connection
"""

import json
import os

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else '.')

from payment_system import WalletManager, PaymentGateway

# Connect to PostgreSQL
import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        database="skillverse_pg",
        user="postgres",
        password="8791"
    )
    cursor = conn.cursor()
    
    # Find Order #64
    cursor.execute('''
        SELECT o.id, o.buyer_id, o.seller_id, o.total_price, s.title
        FROM orders o
        JOIN services s ON o.service_id = s.id
        WHERE o.id = 64
    ''')
    
    order = cursor.fetchone()
    
    if order:
        order_id, buyer_id, seller_id, total_price, service_title = order
        
        print("=" * 60)
        print("ORDER #64 DETAILS")
        print("=" * 60)
        print(f"Order ID: {order_id}")
        print(f"Service: {service_title}")
        print(f"Total Price: Rs.{total_price}")
        print(f"Buyer ID: {buyer_id}")
        print(f"Seller ID: {seller_id}")
        
        seller_amount = float(total_price) * 0.90
        print(f"\nSeller should receive: Rs.{seller_amount:.2f}")
        print("=" * 60)
        
        # Now credit the seller
        gateway = PaymentGateway()
        wallet_mgr = WalletManager(payment_gateway=gateway)
        
        print(f"\nCrediting seller (user_id: {seller_id}) with Rs.{seller_amount}...")
        
        try:
            result = wallet_mgr.credit_seller(
                user_id=seller_id,
                amount=seller_amount,
                description=f'Payment Received: {service_title} (Order #64) - After 10% platform fee [MANUAL FIX]'
            )
            print(f"SUCCESS!")
            print(f"Transaction ID: {result['id']}")
            print(f"Seller new wallet balance: Rs.{result['new_balance']}")
        except Exception as e:
            print(f"ERROR crediting seller: {e}")
    else:
        print("Order #64 not found in database")
    
    conn.close()
    
except Exception as e:
    print(f"Database connection error: {e}")
    print("\nMake sure PostgreSQL is running and the database exists.")
