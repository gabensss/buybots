from flask import Flask, jsonify
from web3 import Web3
import os
import time
import telebot

app = Flask(__name__)

# Configurations
bot_token = os.getenv("7181174197:AAHvFHDGV2xsDD21cZbS2lJs-VQRy7FS5n0")
bot = telebot.TeleBot(bot_token)
CHANNEL_CHAT_ID = os.getenv("CHANNEL_CHAT_ID", "1423231521")
TARGET_ADDRESS = os.getenv("TARGET_ADDRESS", "0xc204af95b0307162118f7bc36a91c9717490ab69")
RPC_URL = os.getenv("RPC_URL", "https://base.drpc.org")
PRIVATE_KEY = os.getenv("92547aed4c5a72d1dfb72ff73720f24696d941beb93c0e02d8ffa29381cf44f3")  # Wallet private key for transactions
WALLET_ADDRESS = os.getenv("0x0c93A5BEC42111403d9E56c999cB53A5F41D72Bc")  # Wallet address for transactions
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Uniswap Router Contract
UNISWAP_ROUTER_ADDRESS = "0x2626664c2603336E57B271c5C0b26F421741e481"  # Replace with actual Uniswap Router address
uniswap_router = w3.eth.contract(address=UNISWAP_ROUTER_ADDRESS, abi=UNISWAP_ROUTER_ABI)  # UNISWAP_ROUTER_ABI is Uniswap’s Router ABI

# Amounts for trading
BUY_AMOUNT_ETH = Web3.toWei(0.005, 'ether')  # 0.005 ETH for purchase
PNL_TARGET = 50  # 50% profit target

# Function to send a Telegram message
def send_telegram_message(message):
    try:
        bot.send_message(CHANNEL_CHAT_ID, message, parse_mode="Markdown")
    except Exception as e:
        print(f"Failed to send message: {e}")

# Function to execute a buy order on Uniswap
def auto_buy_token(token_address):
    try:
        # Set up Uniswap trade parameters
        path = [w3.toChecksumAddress(w3.toHex(w3.eth.coinbase)), w3.toChecksumAddress(token_address)]
        deadline = int(time.time()) + 120  # 2 minutes from now

        # Build transaction
        transaction = uniswap_router.functions.swapExactETHForTokens(
            0,  # Min amount out (can be adjusted for slippage tolerance)
            path,
            WALLET_ADDRESS,
            deadline
        ).buildTransaction({
            'from': WALLET_ADDRESS,
            'value': BUY_AMOUNT_ETH,
            'gas': 2000000,
            'gasPrice': w3.toWei('1', 'gwei'),
            'nonce': w3.eth.getTransactionCount(WALLET_ADDRESS)
        })

        # Sign and send transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)
        txn_hash = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        send_telegram_message(f"Auto-buy order placed: https://etherscan.io/tx/{txn_hash.hex()}")
        return txn_hash
    except Exception as e:
        print(f"Failed to execute buy: {e}")
        return None

# Function to monitor PnL and auto-sell if target is reached
def monitor_and_auto_sell(token_address, buy_amount_eth):
    while True:
        try:
            # Fetch current token balance in wallet
            token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
            balance = token_contract.functions.balanceOf(WALLET_ADDRESS).call()

            # Fetch token price from Uniswap (simplified for example)
            token_price_in_eth = get_token_price_in_eth(token_address)
            current_value = balance * token_price_in_eth

            # Calculate PnL
            pnl = current_value / buy_amount_eth

            # Check if target PnL is reached
            if pnl >= PNL_TARGET:
                send_telegram_message(f"PnL target reached (50% gain). Initiating auto-sell.")
                auto_sell_token(token_address, balance)
                break  # Exit loop after selling
            time.sleep(30)  # Check every 30 seconds

        except Exception as e:
            print(f"Error monitoring PnL: {e}")
            time.sleep(10)

# Function to execute a sell order on Uniswap
def auto_sell_token(token_address, amount):
    try:
        path = [w3.toChecksumAddress(token_address), w3.toChecksumAddress(w3.toHex(w3.eth.coinbase))]
        deadline = int(time.time()) + 30  # 2 minutes from now

        # Build transaction
        transaction = uniswap_router.functions.swapExactTokensForETH(
            amount,
            0,  # Min amount out (adjust for slippage tolerance)
            path,
            WALLET_ADDRESS,
            deadline
        ).buildTransaction({
            'from': WALLET_ADDRESS,
            'gas': 2000000,
            'gasPrice': w3.toWei('1', 'gwei'),
            'nonce': w3.eth.getTransactionCount(WALLET_ADDRESS)
        })

        # Sign and send transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)
        txn_hash = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        send_telegram_message(f"Auto-sell order placed: https://etherscan.io/tx/{txn_hash.hex()}")
    except Exception as e:
        print(f"Failed to execute sell: {e}")

# Monitor for new deployments and initiate auto-buy
def monitor_for_deployments():
    latest_block = w3.eth.block_number

    while True:
        new_block = w3.eth.block_number
        if new_block > latest_block:
            block = w3.eth.get_block(new_block, full_transactions=True)
            for tx in block.transactions:
                if tx['from'].lower() == TARGET_ADDRESS.lower() and tx['to'] is None:
                    receipt = w3.eth.get_transaction_receipt(tx['hash'])
                    contract_address = receipt.contractAddress
                    buy_txn_hash = auto_buy_token(contract_address)
                    if buy_txn_hash:
                        monitor_and_auto_sell(contract_address, BUY_AMOUNT_ETH)
            latest_block = new_block
        time.sleep(3)
