"""
Non-interactive script to diagnose seller payment issue
"""
import json

print("=" * 70)
print("SKILLVERSE - Seller Payment Diagnostic Report")
print("=" * 70)

# Read wallets
print("\n1. CURRENT WALLET BALANCES:")
print("-" * 50)
try:
    with open('wallets.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                wallet = json.loads(line)
                print(f"   User {wallet['user_id']}: Rs.{wallet['balance']:.2f}")
except Exception as e:
    print(f"   Error: {e}")

# Read transactions
print("\n2. RECENT TRANSACTIONS:")
print("-" * 50)
try:
    with open('transactions.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Filter out comments and empty lines
    txn_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('#')]
    
    for line in txn_lines[-10:]:  # Last 10 transactions
        try:
            txn = json.loads(line)
            txn_type = txn.get('type', 'N/A')
            symbol = '+' if txn_type == 'credit' else '-'
            desc = txn.get('description', 'N/A')[:40].replace('\u20b9', 'Rs.')
            print(f"   {txn['id'][:20]}... | User {str(txn['user_id']):>5} | {symbol}Rs.{txn['amount']:>8.2f} | {desc}")
        except Exception as ex:
            print(f"   Parse error: {ex}")
except Exception as e:
    print(f"   Error reading transactions: {e}")

# Check for Order #64 transactions
print("\n3. TRANSACTIONS FOR ORDER #64:")
print("-" * 50)
order_64_debit = None
order_64_credit = None

try:
    with open('transactions.txt', 'r', encoding='utf-8') as f:
        for line in f:
            if 'Order #64' in line:
                txn = json.loads(line)
                if txn.get('type') == 'debit':
                    order_64_debit = txn
                    print(f"   DEBIT (Buyer): User {txn['user_id']} paid Rs.{txn['amount']}")
                elif txn.get('type') == 'credit':
                    order_64_credit = txn
                    print(f"   CREDIT (Seller): User {txn['user_id']} received Rs.{txn['amount']}")
except Exception as e:
    print(f"   Error: {e}")

if order_64_debit and not order_64_credit:
    print("\n   !! ISSUE FOUND: Buyer paid but seller did NOT receive payment!")
    print(f"   Buyer (User {order_64_debit['user_id']}) was charged Rs.{order_64_debit['amount']}")
    expected_seller_amount = order_64_debit['amount'] * 0.90
    print(f"   Seller should have received: Rs.{expected_seller_amount:.2f} (after 10% platform fee)")
elif order_64_debit and order_64_credit:
    print("\n   OK: Both buyer and seller transactions exist.")
else:
    print("\n   No Order #64 found in transactions.")

print("\n" + "=" * 70)
print("END OF DIAGNOSTIC REPORT")
print("=" * 70)
