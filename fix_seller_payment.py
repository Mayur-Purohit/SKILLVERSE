"""
Script to fix missing seller payment for Order #64
and verify the payment system is working correctly.
"""
import sys
import os

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from payment_system import WalletManager, PaymentGateway

# Initialize wallet manager
gateway = PaymentGateway()
wallet_mgr = WalletManager(payment_gateway=gateway)

print("=" * 60)
print("SKILLVERSE - Seller Payment Fix Script")
print("=" * 60)

# First, let's read all wallets to understand the current state
print("\n1. CURRENT WALLET BALANCES:")
print("-" * 40)
with open('wallets.txt', 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            print(f"   {line.strip()}")

print("\n2. REVIEWING RECENT TRANSACTIONS:")
print("-" * 40)
with open('transactions.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    # Show last 5 transaction lines (skip comments)
    txn_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
    for line in txn_lines[-5:]:
        print(f"   {line.strip()}")

# For Order #64:
# - Buyer (user 44) paid ₹880
# - With 10% platform fee: Seller should receive ₹792 (880 * 0.9)
# 
# We need to know the seller_id. Based on the service "1-on-1 Python Programming Lessons", 
# we need to find who owns it. Let's assume it's a different user.

print("\n3. CHECKING FOR MISSING SELLER CREDIT (Order #64):")
print("-" * 40)

# Check if there's already a credit for Order #64
order_64_credit_found = False
with open('transactions.txt', 'r', encoding='utf-8') as f:
    for line in f:
        if 'Order #64' in line and '"type": "credit"' in line:
            order_64_credit_found = True
            print(f"   ✓ Credit transaction found for Order #64")
            break

if not order_64_credit_found:
    print("   ✗ NO credit transaction found for Order #64 - Seller was NOT paid!")
    print("\n   To fix this, you need to:")
    print("   a) Identify the seller's user_id (service owner)")
    print("   b) Credit them ₹792 (880 × 0.90)")
    
    # Let's ask for user input to fix this
    print("\n4. MANUAL FIX:")
    print("-" * 40)
    seller_id = input("   Enter the seller's user_id (or press Enter to skip): ").strip()
    
    if seller_id:
        seller_amount = 880 * 0.90  # ₹792
        print(f"\n   Attempting to credit ₹{seller_amount} to seller user_id={seller_id}...")
        
        try:
            result = wallet_mgr.credit_seller(
                user_id=seller_id,
                amount=seller_amount,
                description='Payment Received: 1-on-1 Python Programming Lessons (1 Hour) (Order #64) - After 10% platform fee [MANUAL FIX]'
            )
            print(f"   ✓ SUCCESS! Seller credited.")
            print(f"   Transaction ID: {result['id']}")
            print(f"   New Balance: ₹{result['new_balance']}")
        except Exception as e:
            print(f"   ✗ ERROR: {str(e)}")
    else:
        print("   Skipped manual fix.")
else:
    print("   Order #64 seller payment is already processed.")

print("\n5. FINAL WALLET BALANCES:")
print("-" * 40)
with open('wallets.txt', 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            print(f"   {line.strip()}")

print("\n" + "=" * 60)
print("Script completed. The order placement code has been fixed")
print("to ensure sellers receive payment for future orders.")
print("=" * 60)
