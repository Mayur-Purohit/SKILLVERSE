"""
Payment System Module for SkillVerse Application

This module implements a Mock Payment Gateway and Wallet System
using ONLY Python syllabus concepts for educational purposes.

SYLLABUS UNITS COVERED:
- Unit-6: File Handling (txt file read/write)
- Unit-7: datetime module for timestamps
- Unit-8: Exception Handling, OOP basics
- Unit-9: Classes, Objects, Inheritance

Author: SkillVerse Team
Date: January 2026
"""

import json                    # Unit-7: Built-in modules
import random                  # Unit-7: Built-in modules
from datetime import datetime  # Unit-7: datetime module
import os                      # Unit-7: os module for file paths


# ============================================================================
# CUSTOM EXCEPTION CLASSES (Unit-8: Exception Handling)
# ============================================================================

class CustomException(Exception):
    """
    Base custom exception class for the payment system.
    
    OOP Concept: INHERITANCE (Unit-9)
    - Inherits from built-in Exception class
    - Used as base for all payment-related exceptions
    """
    pass


class InsufficientBalanceException(CustomException):
    """
    Exception raised when wallet balance is insufficient for a transaction.
    
    OOP Concept: MULTI-LEVEL INHERITANCE
    - Inherits from CustomException
    - Represents specific error case
    """
    def __init__(self, required, available):
        self.required = required
        self.available = available
        super().__init__(f"Insufficient balance: Required ₹{required}, Available ₹{available}")


class InvalidCardException(CustomException):
    """
    Exception raised when card details are invalid.
    """
    def __init__(self, message="Invalid card details provided"):
        super().__init__(message)


class TransactionNotFoundException(CustomException):
    """
    Exception raised when a transaction is not found.
    """
    def __init__(self, txn_id):
        super().__init__(f"Transaction not found: {txn_id}")


# ============================================================================
# PAYMENT GATEWAY CLASS (Unit-8, 9: OOP)
# ============================================================================

class PaymentGateway:
    """
    Mock Payment Gateway for processing transactions.
    
    OOP Concepts Demonstrated:
    - ENCAPSULATION: Private attributes like __success_rate
    - CONSTRUCTOR: __init__ method
    - INSTANCE METHODS: process_payment, save_transaction, etc.
    
    File Handling (Unit-6):
    - Stores transactions in text file
    - Uses JSON format for data serialization
    """
    
    def __init__(self, transactions_file='transactions.txt'):
        """
        Constructor (Unit-9: __init__ method)
        
        Args:
            transactions_file: Path to transactions file (default: transactions.txt)
        """
        self.__success_rate = 1.0  # Private attribute (100% success rate - payments always succeed)
        self.transactions_file = transactions_file
        self.__ensure_file_exists()
    
    def __ensure_file_exists(self):
        """
        Private method to create file if it doesn't exist.
        
        File Handling (Unit-6): Creating files
        """
        if not os.path.exists(self.transactions_file):
            try:
                with open(self.transactions_file, 'w') as f:
                    pass  # Create empty file
            except IOError as e:
                raise CustomException(f"Error creating transactions file: {e}")
    
    def generate_transaction_id(self):
        """
        Generate unique transaction ID using datetime.
        
        datetime Module (Unit-7):
        - Uses strftime to format date/time
        - Creates unique ID with timestamp
        
        Returns:
            str: Transaction ID in format TXN + YYYYMMDDHHMMSS + random number
        """
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = random.randint(100, 999)
        return f"TXN{timestamp}{random_suffix}"
    
    def validate_card(self, card_number, expiry_date, cvv):
        """
        Validate credit/debit card details.
        
        Args:
            card_number: 16-digit card number
            expiry_date: Expiry date in MM/YY format
            cvv: 3-digit CVV
            
        Returns:
            bool: True if valid, raises exception otherwise
            
        Raises:
            InvalidCardException: If card details are invalid
        """
        # Validate card number (16 digits)
        if not card_number or len(card_number.replace(' ', '')) != 16:
            raise InvalidCardException("Card number must be 16 digits")
        
        if not card_number.replace(' ', '').isdigit():
            raise InvalidCardException("Card number must contain only digits")
        
        # Validate CVV (3 digits)
        if not cvv or len(cvv) != 3 or not cvv.isdigit():
            raise InvalidCardException("CVV must be 3 digits")
        
        # Validate expiry date (MM/YY format)
        if not expiry_date or len(expiry_date) != 5 or expiry_date[2] != '/':
            raise InvalidCardException("Expiry date must be in MM/YY format")
        
        try:
            month = int(expiry_date[:2])
            year = int(expiry_date[3:])
            
            if month < 1 or month > 12:
                raise InvalidCardException("Invalid expiry month")
            
            current_year = datetime.now().year % 100
            current_month = datetime.now().month
            
            if year < current_year or (year == current_year and month < current_month):
                raise InvalidCardException("Card has expired")
                
        except ValueError:
            raise InvalidCardException("Invalid expiry date format")
        
        return True
    
    def process_payment(self, amount, payment_method, user_id, description=""):
        """
        Process a payment with 80% success rate simulation.
        
        Args:
            amount: Transaction amount in rupees
            payment_method: 'card', 'upi', 'netbanking', or 'wallet'
            user_id: ID of the user making payment
            description: Transaction description
            
        Returns:
            dict: Transaction result with status, txn_id, etc.
        """
        # Generate transaction ID
        txn_id = self.generate_transaction_id()
        
        # Simulate 80% success rate using random (Unit-7)
        success = random.random() < self.__success_rate
        status = 'success' if success else 'failed'
        
        # Create transaction data
        txn_data = {
            'id': txn_id,
            'user_id': user_id,
            'amount': float(amount),
            'method': payment_method,
            'status': status,
            'description': description,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'timestamp': datetime.now().isoformat()
        }
        
        # Save transaction to file
        self.save_transaction(txn_data)
        
        return txn_data
    
    def save_transaction(self, txn_data):
        """
        Save transaction to text file.
        
        File Handling (Unit-6):
        - Opens file in append mode ('a')
        - Writes JSON data with newline
        
        Args:
            txn_data: Dictionary containing transaction details
            
        Raises:
            CustomException: If file write fails
        """
        try:
            # File Handling: Opening file in append mode
            with open(self.transactions_file, 'a', encoding='utf-8') as f:
                # Convert dict to JSON string and write
                f.write(json.dumps(txn_data) + '\n')
        except IOError as e:
            raise CustomException(f"Error saving transaction: {e}")
        except json.JSONEncodeError as e:
            raise CustomException(f"Error encoding transaction data: {e}")
    
    def get_transaction(self, txn_id, user_id=None):
        """
        Retrieve a specific transaction by ID.
        
        File Handling (Unit-6):
        - Opens file in read mode ('r')
        - Reads line by line
        
        Args:
            txn_id: Transaction ID to search for
            user_id: Optional User ID to filter by (for shared IDs)
            
        Returns:
            dict: Transaction data if found
            
        Raises:
            TransactionNotFoundException: If transaction not found
        """
        try:
            with open(self.transactions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        txn = json.loads(line)
                        if txn.get('id') == txn_id:
                            # If user_id is provided, ensure it matches
                            if user_id and str(txn.get('user_id')) != str(user_id):
                                continue
                            return txn
            raise TransactionNotFoundException(txn_id)
        except IOError as e:
            raise CustomException(f"Error reading transactions: {e}")
        except json.JSONDecodeError:
            pass  # Skip malformed lines
    
    def get_user_transactions(self, user_id):
        """
        Get all transactions for a specific user.
        
        File Handling (Unit-6):
        - Reads entire file
        - Filters by user_id
        
        Args:
            user_id: User ID to filter by
            
        Returns:
            list: List of transaction dictionaries
        """
        transactions = []
        try:
            if os.path.exists(self.transactions_file):
                with open(self.transactions_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                txn = json.loads(line)
                                if str(txn.get('user_id')) == str(user_id):
                                    transactions.append(txn)
                            except json.JSONDecodeError:
                                continue  # Skip malformed lines
        except IOError as e:
            raise CustomException(f"Error reading transactions: {e}")
        
        # Sort by timestamp (newest first)
        transactions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return transactions
    
    def get_all_transactions(self):
        """
        Get all transactions from file.
        
        Returns:
            list: List of all transaction dictionaries
        """
        transactions = []
        try:
            if os.path.exists(self.transactions_file):
                with open(self.transactions_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                txn = json.loads(line)
                                transactions.append(txn)
                            except json.JSONDecodeError:
                                continue
        except IOError as e:
            raise CustomException(f"Error reading transactions: {e}")
        
        transactions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return transactions


# ============================================================================
# WALLET MANAGER CLASS (Unit-8, 9: OOP)
# ============================================================================

class WalletManager:
    """
    Wallet Management System for handling user balances.
    
    OOP Concepts Demonstrated:
    - COMPOSITION: Uses PaymentGateway for transactions
    - ENCAPSULATION: Private methods and attributes
    - METHODS: get_balance, add_money, deduct_money
    
    File Handling (Unit-6):
    - Stores wallet data in text file
    - Each line represents a user's wallet
    """
    
    def __init__(self, wallet_file='wallets.txt', payment_gateway=None):
        """
        Initialize WalletManager.
        
        Args:
            wallet_file: Path to wallet data file
            payment_gateway: PaymentGateway instance for transactions
        """
        self.wallet_file = wallet_file
        # COMPOSITION: WalletManager HAS-A PaymentGateway
        self.payment_gateway = payment_gateway or PaymentGateway()
        self.__ensure_file_exists()
    
    def __ensure_file_exists(self):
        """Create wallet file if it doesn't exist."""
        if not os.path.exists(self.wallet_file):
            try:
                with open(self.wallet_file, 'w', encoding='utf-8') as f:
                    pass
            except IOError as e:
                raise CustomException(f"Error creating wallet file: {e}")
    
    def __read_all_wallets(self):
        """
        Read all wallet data from file.
        
        File Handling (Unit-6): Reading entire file
        
        Returns:
            dict: Dictionary mapping user_id to wallet data
        """
        wallets = {}
        try:
            with open(self.wallet_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            wallet = json.loads(line)
                            user_id = str(wallet.get('user_id'))
                            wallets[user_id] = wallet
                        except json.JSONDecodeError:
                            continue
        except IOError as e:
            raise CustomException(f"Error reading wallets: {e}")
        return wallets
    
    def __write_all_wallets(self, wallets):
        """
        Write all wallet data to file.
        
        File Handling (Unit-6): Writing to file (overwrite mode)
        
        Args:
            wallets: Dictionary of all wallet data
        """
        try:
            with open(self.wallet_file, 'w', encoding='utf-8') as f:
                for wallet in wallets.values():
                    f.write(json.dumps(wallet) + '\n')
        except IOError as e:
            raise CustomException(f"Error writing wallets: {e}")
    
    def get_balance(self, user_id):
        """
        Get current wallet balance for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            float: Current balance (0 if wallet doesn't exist)
        """
        wallets = self.__read_all_wallets()
        user_id = str(user_id)
        
        if user_id in wallets:
            return float(wallets[user_id].get('balance', 0))
        return 0.0
    
    def get_wallet(self, user_id):
        """
        Get complete wallet data for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            dict: Wallet data including balance and history
        """
        wallets = self.__read_all_wallets()
        user_id = str(user_id)
        
        if user_id in wallets:
            return wallets[user_id]
        
        # Return default wallet structure if not exists
        return {
            'user_id': user_id,
            'balance': 0.0,
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
    
    def create_wallet(self, user_id, initial_balance=0):
        """
        Create a new wallet for a user.
        
        Args:
            user_id: User ID
            initial_balance: Starting balance (default 0)
            
        Returns:
            dict: Created wallet data
        """
        wallets = self.__read_all_wallets()
        user_id = str(user_id)
        
        if user_id not in wallets:
            wallets[user_id] = {
                'user_id': user_id,
                'balance': float(initial_balance),
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            self.__write_all_wallets(wallets)
        
        return wallets[user_id]
    
    def add_money(self, user_id, amount, payment_method='card', description='Wallet Recharge'):
        """
        Add money to wallet using payment gateway.
        
        Exception Handling (Unit-8):
        - Validates amount
        - Handles payment failure
        
        Args:
            user_id: User ID
            amount: Amount to add
            payment_method: Payment method used
            description: Transaction description
            
        Returns:
            dict: Transaction result
            
        Raises:
            CustomException: If amount is invalid or payment fails
        """
        # Validate amount
        if amount <= 0:
            raise CustomException("Amount must be greater than 0")
        
        # Process payment through gateway
        txn_result = self.payment_gateway.process_payment(
            amount=amount,
            payment_method=payment_method,
            user_id=user_id,
            description=description
        )
        
        # Only add to wallet if payment succeeded
        if txn_result['status'] == 'success':
            wallets = self.__read_all_wallets()
            user_id = str(user_id)
            
            if user_id not in wallets:
                wallets[user_id] = {
                    'user_id': user_id,
                    'balance': 0.0,
                    'created_at': datetime.now().isoformat()
                }
            
            # Update balance
            wallets[user_id]['balance'] = float(wallets[user_id].get('balance', 0)) + float(amount)
            wallets[user_id]['last_updated'] = datetime.now().isoformat()
            
            self.__write_all_wallets(wallets)
            txn_result['new_balance'] = wallets[user_id]['balance']
        
        return txn_result
    
    def deduct_money(self, user_id, amount, description='Service Purchase', username=None):
        """
        Deduct money from wallet for purchase.
        
        Exception Handling (Unit-8):
        - Checks sufficient balance
        - Raises InsufficientBalanceException if needed
        
        Args:
            user_id: User ID
            amount: Amount to deduct
            description: Transaction description
            username: Username for display
            
        Returns:
            dict: Transaction result
        """
        if amount <= 0:
            raise CustomException("Amount must be greater than 0")
        
        wallets = self.__read_all_wallets()
        user_id = str(user_id)
        
        current_balance = 0
        if user_id in wallets:
            current_balance = float(wallets[user_id].get('balance', 0))
        
        # Check sufficient balance
        if current_balance < amount:
            raise InsufficientBalanceException(required=amount, available=current_balance)
        
        # Deduct amount
        wallets[user_id]['balance'] = current_balance - float(amount)
        wallets[user_id]['last_updated'] = datetime.now().isoformat()
        
        self.__write_all_wallets(wallets)
        
        # Record transaction
        txn_result = {
            'id': self.payment_gateway.generate_transaction_id(),
            'user_id': user_id,
            'username': username or f'User #{user_id}',
            'amount': float(amount),
            'method': 'wallet',
            'status': 'success',
            'type': 'debit',
            'description': description,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'timestamp': datetime.now().isoformat(),
            'new_balance': wallets[user_id]['balance']
        }
        
        self.payment_gateway.save_transaction(txn_result)
        
        return txn_result
    
    def credit_seller(self, user_id, amount, description='Payment Received', username=None, transaction_id=None):
        """
        Credit money to seller's wallet when a purchase is made.
        
        Args:
            user_id: Seller's user ID
            amount: Amount to credit
            description: Transaction description
            username: Seller's username
            transaction_id: ID to use for transaction (shared with buyer)
            
        Returns:
            dict: Transaction result
        """
        if amount <= 0:
            raise CustomException("Amount must be greater than 0")
        
        wallets = self.__read_all_wallets()
        user_id = str(user_id)
        
        # Create wallet if doesn't exist
        if user_id not in wallets:
            wallets[user_id] = {
                'user_id': user_id,
                'balance': 0.0,
                'created_at': datetime.now().isoformat()
            }
        
        # Add amount to seller's wallet
        wallets[user_id]['balance'] = float(wallets[user_id].get('balance', 0)) + float(amount)
        wallets[user_id]['last_updated'] = datetime.now().isoformat()
        
        self.__write_all_wallets(wallets)
        
        # Record transaction as credit for seller
        txn_result = {
            'id': transaction_id or self.payment_gateway.generate_transaction_id(),
            'user_id': user_id,
            'username': username or f'User #{user_id}',
            'amount': float(amount),
            'method': 'wallet',
            'status': 'success',
            'type': 'credit',
            'description': description,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'timestamp': datetime.now().isoformat(),
            'new_balance': wallets[user_id]['balance']
        }
        
        self.payment_gateway.save_transaction(txn_result)
        
        return txn_result
    
    def get_transaction_history(self, user_id):
        """
        Get wallet transaction history for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            list: List of transactions (sorted by date, newest first)
        """
        return self.payment_gateway.get_user_transactions(user_id)


# ============================================================================
# INVOICE GENERATOR CLASS (Unit-9: OOP)
# ============================================================================

class InvoiceGenerator:
    """
    Generate HTML invoices for transactions.
    
    OOP Concept: Single Responsibility Principle
    - This class only handles invoice generation
    - Uses template strings for HTML generation
    
    File Handling (Unit-6):
    - Creates HTML files for invoices
    """
    
    def __init__(self, invoices_folder='invoices'):
        """
        Initialize InvoiceGenerator.
        
        Args:
            invoices_folder: Folder to store generated invoices
        """
        self.invoices_folder = invoices_folder
        self.__ensure_folder_exists()
    
    def __ensure_folder_exists(self):
        """Create invoices folder if it doesn't exist."""
        if not os.path.exists(self.invoices_folder):
            try:
                os.makedirs(self.invoices_folder)
            except OSError as e:
                raise CustomException(f"Error creating invoices folder: {e}")
    
    def generate_invoice_html(self, transaction):
        """
        Generate HTML invoice content for a transaction.
        
        String Formatting (Unit-3):
        - Uses f-strings for template
        - Creates formatted HTML document
        
        Args:
            transaction: Transaction dictionary
            
        Returns:
            str: HTML content of invoice
        """
        # Transaction details
        txn_id = transaction.get('id', 'N/A')
        amount = transaction.get('amount', 0)
        status = transaction.get('status', 'N/A')
        method = transaction.get('method', 'N/A')
        date = transaction.get('date', 'N/A')
        time = transaction.get('time', 'N/A')
        description = transaction.get('description', 'Service Transaction')
        user_id = transaction.get('user_id', 'N/A')
        username = transaction.get('username', f'User #{user_id}')
        
        # Clean up description - remove specific internal tags like [MANUAL FIX]
        import re
        description = re.sub(r'\s*\[MANUAL FIX\]\s*', '', description, flags=re.IGNORECASE).strip()
        
        # Status color
        status_color = '#28a745' if status == 'success' else '#dc3545'
        
        # Generate HTML using f-string (Unit-3)
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoice - {txn_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .invoice-container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            overflow: hidden;
        }}
        .invoice-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .invoice-header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}
        .invoice-header p {{
            opacity: 0.9;
            font-size: 1.1rem;
        }}
        .invoice-body {{
            padding: 40px;
        }}
        .invoice-info {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px dashed #e0e0e0;
        }}
        .info-block h3 {{
            color: #667eea;
            margin-bottom: 10px;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .info-block p {{
            font-size: 1rem;
            color: #333;
        }}
        .transaction-details {{
            background: #f8f9fa;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
        }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 15px 0;
            border-bottom: 1px solid #e0e0e0;
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            color: #666;
            font-weight: 500;
        }}
        .detail-value {{
            color: #333;
            font-weight: 600;
        }}
        .amount-section {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            margin-bottom: 30px;
        }}
        .amount-section h2 {{
            font-size: 1rem;
            opacity: 0.9;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        .amount-section .amount {{
            font-size: 3rem;
            font-weight: 700;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 20px;
            border-radius: 25px;
            font-size: 0.9rem;
            font-weight: 600;
            text-transform: uppercase;
            background: {status_color};
            color: white;
        }}
        .invoice-footer {{
            text-align: center;
            padding: 30px;
            background: #f8f9fa;
            color: #666;
        }}
        .invoice-footer p {{
            margin-bottom: 10px;
        }}
        .brand {{
            color: #667eea;
            font-weight: 700;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .invoice-container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="invoice-container">
        <div class="invoice-header">
            <h1>📋 INVOICE</h1>
            <p>SkillVerse Payment Receipt</p>
        </div>
        
        <div class="invoice-body">
            <div class="invoice-info">
                <div class="info-block">
                    <h3>Transaction ID</h3>
                    <p>{txn_id}</p>
                </div>
                <div class="info-block">
                    <h3>Date & Time</h3>
                    <p>{date} at {time}</p>
                </div>
                <div class="info-block">
                    <h3>Status</h3>
                    <p><span class="status-badge">{status.upper()}</span></p>
                </div>
            </div>
            
            <div class="amount-section">
                <h2>Total Amount</h2>
                <div class="amount">₹{amount:,.2f}</div>
            </div>
            
            <div class="transaction-details">
                <div class="detail-row">
                    <span class="detail-label">Description</span>
                    <span class="detail-value">{description}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Payment Method</span>
                    <span class="detail-value">{method.upper()}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Customer</span>
                    <span class="detail-value">{username}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Transaction Date</span>
                    <span class="detail-value">{date}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Transaction Time</span>
                    <span class="detail-value">{time}</span>
                </div>
            </div>
        </div>
        
        <div class="invoice-footer">
            <p>Thank you for using <span class="brand">SkillVerse</span>!</p>
            <p>This is a computer-generated invoice. No signature required.</p>
            <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>"""
        
        return html_content
    
    def save_invoice(self, transaction):
        """
        Save invoice as HTML file.
        
        File Handling (Unit-6):
        - Creates HTML file with invoice content
        
        Args:
            transaction: Transaction dictionary
            
        Returns:
            str: Path to saved invoice file
        """
        txn_id = transaction.get('id', 'unknown')
        html_content = self.generate_invoice_html(transaction)
        
        file_path = os.path.join(self.invoices_folder, f"invoice_{txn_id}.html")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return file_path
        except IOError as e:
            raise CustomException(f"Error saving invoice: {e}")


# ============================================================================
# TRANSACTION FILTER CLASS (Additional Utility)
# ============================================================================

class TransactionFilter:
    """
    Utility class for filtering and exporting transactions.
    
    OOP Concept: Utility/Helper class
    - Contains static-like methods for transaction operations
    """
    
    @staticmethod
    def filter_by_date_range(transactions, start_date, end_date):
        """
        Filter transactions by date range.
        
        Args:
            transactions: List of transaction dictionaries
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            
        Returns:
            list: Filtered transactions
        """
        filtered = []
        for txn in transactions:
            txn_date = txn.get('date', '')
            if start_date <= txn_date <= end_date:
                filtered.append(txn)
        return filtered
    
    @staticmethod
    def filter_by_status(transactions, status):
        """
        Filter transactions by status.
        
        Args:
            transactions: List of transaction dictionaries
            status: Status to filter by ('success' or 'failed')
            
        Returns:
            list: Filtered transactions
        """
        return [txn for txn in transactions if txn.get('status') == status]
    
    @staticmethod
    def export_to_csv(transactions, filename='transactions.csv'):
        """
        Export transactions to CSV file.
        
        File Handling (Unit-6):
        - Creates CSV formatted file
        
        Args:
            transactions: List of transaction dictionaries
            filename: Output CSV filename
            
        Returns:
            str: CSV content as string
        """
        if not transactions:
            return "No transactions to export"
        
        # CSV Header
        headers = ['Transaction ID', 'Amount', 'Status', 'Method', 'Description', 'Date', 'Time']
        csv_content = ','.join(headers) + '\n'
        
        # CSV Rows
        for txn in transactions:
            row = [
                str(txn.get('id', '')),
                str(txn.get('amount', '')),
                str(txn.get('status', '')),
                str(txn.get('method', '')),
                str(txn.get('description', '')).replace(',', ';'),  # Escape commas
                str(txn.get('date', '')),
                str(txn.get('time', ''))
            ]
            csv_content += ','.join(row) + '\n'
        
        # Save to file
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(csv_content)
        except IOError as e:
            raise CustomException(f"Error exporting CSV: {e}")
        
        return csv_content


# ============================================================================
# EXAMPLE USAGE (For Testing)
# ============================================================================

if __name__ == "__main__":
    """
    Example usage demonstrating all features.
    
    This section only runs when the file is executed directly,
    not when imported as a module.
    """
    
    print("=" * 60)
    print("SkillVerse Payment System - Demo")
    print("=" * 60)
    
    # Initialize components
    gateway = PaymentGateway()
    wallet = WalletManager(payment_gateway=gateway)
    invoice_gen = InvoiceGenerator()
    
    # Demo user
    demo_user_id = "user_demo_123"
    
    # 1. Create wallet
    print("\n1. Creating wallet...")
    wallet.create_wallet(demo_user_id, initial_balance=100)
    print(f"   Wallet created with balance: ₹{wallet.get_balance(demo_user_id)}")
    
    # 2. Add money
    print("\n2. Adding money to wallet...")
    try:
        result = wallet.add_money(demo_user_id, 500, 'card', 'Test Recharge')
        print(f"   Transaction: {result['id']}")
        print(f"   Status: {result['status']}")
        if result['status'] == 'success':
            print(f"   New Balance: ₹{result.get('new_balance', 'N/A')}")
    except CustomException as e:
        print(f"   Error: {e}")
    
    # 3. Check balance
    print("\n3. Current wallet balance:")
    print(f"   Balance: ₹{wallet.get_balance(demo_user_id)}")
    
    # 4. Deduct money
    print("\n4. Making a purchase...")
    try:
        result = wallet.deduct_money(demo_user_id, 200, 'Course Purchase')
        print(f"   Transaction: {result['id']}")
        print(f"   Status: {result['status']}")
        print(f"   New Balance: ₹{result.get('new_balance', 'N/A')}")
    except InsufficientBalanceException as e:
        print(f"   Error: {e}")
    
    # 5. Get transaction history
    print("\n5. Transaction History:")
    history = wallet.get_transaction_history(demo_user_id)
    for txn in history[:5]:
        print(f"   - {txn['id']}: ₹{txn['amount']} ({txn['status']})")
    
    # 6. Generate invoice
    print("\n6. Generating invoice...")
    if history:
        invoice_path = invoice_gen.save_invoice(history[0])
        print(f"   Invoice saved to: {invoice_path}")
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
