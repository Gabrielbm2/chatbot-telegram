import os
import sys
import ssl
import json
import time
import logging
import asyncio
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import get_user, update_user, create_user_if_not_exists, add_transaction, get_transactions
from telegram.error import Conflict
from io import BytesIO

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

start_time = time.time()

TELEGRAM_TOKEN = '7997468263:AAEbyi_YttRUKAOWemjaBXA1nQ-APkADvz0'
if not TELEGRAM_TOKEN:
    raise ValueError(
        "Telegram token not found. Please ensure the TELEGRAM_TOKEN environment variable is correctly set.")


def get_uptime():
    elapsed_time = time.time() - start_time
    return elapsed_time


def build_menu(buttons, n_cols):
    return [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]


async def show_main_menu(update_or_query, context):
    keyboard = [
        InlineKeyboardButton("Check Balance", callback_data='check_balance'),
        InlineKeyboardButton("Deposit", callback_data='deposit'),
        InlineKeyboardButton("Withdraw", callback_data='withdraw'),
        InlineKeyboardButton('Cancel', callback_data='cancel')
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(keyboard, 1))
    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text('Welcome to Mock Bank! Choose an option:', reply_markup=reply_markup)
    else:
        await update_or_query.edit_message_text('Choose an option:', reply_markup=reply_markup)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    create_user_if_not_exists(user_id)
    await show_main_menu(update, context)


def add_unique_method(user_id, method):
    user = get_user(user_id)
    methods = user.get('deposit_methods', [])
    if not any(m['type'] == method['type'] and m.get('crypto_type') == method.get('crypto_type') and m['details'] ==
               method['details'] for m in methods):
        update_user(user_id, {"$push": {"deposit_methods": method}})


async def debug_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Restarting bot...")
    os.execv(sys.executable, ['python'] + sys.argv)


async def debug_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uptime_seconds = get_uptime()
    uptime_message = f"Bot has been running for {uptime_seconds:.2f} seconds."
    await update.message.reply_text(uptime_message)


def calculate_detailed_balance(user_id):
    transactions = get_transactions(user_id)

    fiat_balance = 0.0
    crypto_balances = defaultdict(float)

    for transaction in transactions:
        if transaction["type"] == "deposit":
            amount = float(transaction["value"])
            if transaction["method"] in ["bank_transfer", "paypal"]:
                fiat_balance += amount
            elif transaction["method"] == "crypto":
                crypto_balances[transaction["currency"]] += amount
        elif transaction["type"] == "withdraw":
            amount = float(transaction["value"])
            if transaction["method"] in ["bank_transfer", "paypal"]:
                fiat_balance -= amount
            elif transaction["method"] == "crypto":
                crypto_balances[transaction["currency"]] -= amount

    total_balance = fiat_balance + sum(crypto_balances.values())

    return {
        "fiat_balance": fiat_balance,
        "crypto_balances": dict(crypto_balances),
        "total_balance": total_balance
    }


async def show_user_balance(update_or_query, context, user_id):
    balance_details = calculate_detailed_balance(user_id)
    fiat_balance = balance_details["fiat_balance"]
    crypto_balances = balance_details["crypto_balances"]

    balance_message = f"Fiat Balance (Bank & PayPal): ${fiat_balance:.2f}\n\nCrypto Balances:\n"
    for crypto_type, amount in crypto_balances.items():
        balance_message += f"- {crypto_type}: {amount:.2f}\n"

    balance_message += f"\nTotal Balance: ${balance_details['total_balance']:.2f}"

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(
            text=balance_message,
            reply_markup=InlineKeyboardMarkup(
                build_menu([InlineKeyboardButton("Back to Main Menu", callback_data='back_to_menu')], 1)
            )
        )
    else:
        await update_or_query.edit_message_text(
            text=balance_message,
            reply_markup=InlineKeyboardMarkup(
                build_menu([InlineKeyboardButton("Back to Main Menu", callback_data='back_to_menu')], 1)
            )
        )


async def show_payment_methods(update_or_query, context, user_id):
    user = get_user(user_id)
    methods = user.get("deposit_methods", [])

    buttons = [
        InlineKeyboardButton(f"{method['type']} ({method.get('details', '')})",
                             callback_data=f"use_method_{method['type']}_")
        for method in methods
    ]
    buttons.append(InlineKeyboardButton("Add Payment Method", callback_data='add_payment_method'))
    buttons.append(InlineKeyboardButton("Cancel", callback_data='cancel'))
    reply_markup = InlineKeyboardMarkup(build_menu(buttons, 1))

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text("Select a payment method:", reply_markup=reply_markup)
    else:
        await update_or_query.edit_message_text("Select a payment method:", reply_markup=reply_markup)


def validate_transaction_data(state):
    flow = state.get("flow")
    amount = state.get("amount")
    method = state.get("selected_method_type")

    if not flow or amount is None or not method:
        return False
    return True


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    state = user.get("state", {})

    if not state:
        state = {}

    try:
        if query.data == 'check_balance':
            await show_user_balance(query, context, user_id)
        elif query.data == 'deposit':
            update_user(user_id, {"state": {"flow": "deposit", "step": 1}})
            await query.edit_message_text("Enter the amount to deposit:")
        elif query.data == 'withdraw':
            update_user(user_id, {"state": {"flow": "withdraw", "step": 1}})
            await query.edit_message_text("Enter the amount to withdraw:")
        elif query.data == 'back_to_menu':
            await show_main_menu(query, context)
        elif query.data == 'add_payment_method':
            update_user(user_id, {"state.step": 2})
            await query.edit_message_text(
                text="Choose a method type:",
                reply_markup=InlineKeyboardMarkup(
                    build_menu([
                        InlineKeyboardButton("Bank Transfer", callback_data='bank_transfer'),
                        InlineKeyboardButton("Paypal", callback_data='paypal'),
                        InlineKeyboardButton("Crypto", callback_data='crypto'),
                        InlineKeyboardButton('Cancel', callback_data='cancel')
                    ], 1)
                )
            )
        elif query.data == 'bank_transfer':
            update_user(user_id, {"state.selected_method_type": query.data, "state.step": 3})
            await query.edit_message_text("Enter the name of the bank:")
        elif query.data == 'paypal':
            update_user(user_id, {"state.selected_method_type": query.data, "state.step": 3})
            await query.edit_message_text("Enter your Paypal e-mail address:")
        elif query.data == 'crypto':
            update_user(user_id, {"state.selected_method_type": query.data, "state.step": 3})
            await query.edit_message_text(
                text="Choose a Crypto type:",
                reply_markup=InlineKeyboardMarkup(
                    build_menu([
                        InlineKeyboardButton("BTC", callback_data='btc'),
                        InlineKeyboardButton("ETH", callback_data='eth'),
                        InlineKeyboardButton("USDT", callback_data='usdt'),
                        InlineKeyboardButton('Cancel', callback_data='cancel')
                    ], 1)
                )
            )
        elif query.data in ['btc', 'eth', 'usdt']:
            update_user(user_id, {"state.selected_crypto_type": query.data, "state.step": 4})
            await query.edit_message_text(text=f"Enter your {query.data.upper()} address:")
        elif query.data == 'cancel':
            await query.edit_message_text("Operation cancelled. Thank you for using Mock Bank. Goodbye!")
            return
        elif query.data == 'confirm_yes':
            if not validate_transaction_data(state):
                await query.edit_message_text("An error occurred: Flow, amount, or method is not defined.")
                return

            flow = state.get("flow")
            amount = state.get("amount")
            method_type = state.get("selected_method_type")
            method_details = state.get("selected_method_details", "")

            try:
                meio = method_type
                currency = "USD"
                valor = amount

                if flow == "deposit":
                    add_transaction(user_id, "deposit", meio, currency, valor)
                    await query.edit_message_text(
                        f"Deposited {amount} using {method_type}. Thank you for using Mock Bank. Goodbye!")
                elif flow == "withdraw":
                    if method_type in ['bank_transfer', 'paypal']:
                        fiat_balance = calculate_detailed_balance(user_id)['fiat_balance']
                        if valor > fiat_balance:
                            await query.edit_message_text(
                                f"Insufficient fiat balance for {method_type}. Withdrawal denied."
                            )
                            return

                    elif method_type == 'crypto':
                        crypto_type = state.get("selected_crypto_type", "").upper()
                        if valor > calculate_detailed_balance(user_id)['crypto_balances'].get(crypto_type, 0):
                            await query.edit_message_text(
                                f"Insufficient {crypto_type} balance. Withdrawal denied."
                            )
                            return

                    add_transaction(user_id, "withdraw", meio, currency, valor)
                    await query.edit_message_text(
                        f"Withdrawn {amount} using {method_type}. Thank you for using Mock Bank. Goodbye!")

                update_user(user_id, {"$unset": {"state": ""}})
            except Exception as e:
                await query.edit_message_text(
                    "An error occurred while processing your transaction. Please try again later.")
            return

        elif query.data == 'confirm_no':
            update_user(user_id, {"$unset": {"state": ""}})
            await query.edit_message_text("Operation cancelled. Thank you for using Mock Bank. Goodbye!")
            return
        else:
            import re
            match = re.match(r'use_method_(\w+)_', query.data)
            if match:
                method_type = match.group(1)
                selected_method = next(
                    (method for method in user['deposit_methods'] if method['type'] == method_type), None)
                if selected_method:
                    update_user(user_id, {"state.selected_method_type": selected_method['type'],
                                          "state.selected_method_details": selected_method['details'], "state.step": 4})
                    await query.edit_message_text(
                        text=f"Confirm {state.get('flow')} of {state.get('amount')} using {selected_method['type']} ({selected_method['details']})?",
                        reply_markup=InlineKeyboardMarkup(
                            build_menu([
                                InlineKeyboardButton("Yes", callback_data='confirm_yes'),
                                InlineKeyboardButton("No", callback_data='confirm_no')
                            ], 2)
                        )
                    )
                else:
                    await query.edit_message_text("An error occurred. Selected method not found.")
    except Exception as e:
        await query.edit_message_text("An error occurred. Please try again later.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    state = user.get("state", {})

    if not state:
        state = {}

    user_input = update.message.text

    try:
        if state.get("flow") == "deposit" and state.get("step") == 1:
            if not user_input.isdigit() or int(user_input) <= 0:
                await update.message.reply_text("Enter a valid positive integer for deposit amount.")
                return

            amount = int(user_input)
            update_user(user_id, {"state.amount": amount, "state.step": 2})
            await show_payment_methods(update, context, user_id)

        elif state.get("flow") == "deposit" and state.get("step") == 4:
            method_type = state.get("selected_method_type")
            crypto_type = state.get("selected_crypto_type", "").upper()
            amount = state.get("amount")

            if method_type == 'crypto' and crypto_type:
                add_unique_method(user_id, {
                    "type": "crypto",
                    "crypto_type": crypto_type,
                    "details": user_input
                })
                update_user(user_id, {"state": {"flow": "deposit", "step": 2}})
                await show_payment_methods(update, context, user_id)

        elif state.get("flow") == "deposit" and state.get("step") == 3:
            method_type = state.get("selected_method_type")

            if method_type == 'bank_transfer':
                add_unique_method(user_id, {"type": "bank_transfer", "details": user_input})
                update_user(user_id, {"state.selected_method_details": user_input, "state.step": 4})
                await show_payment_methods(update, context, user_id)

            elif method_type == 'paypal':
                add_unique_method(user_id, {"type": "paypal", "details": user_input})
                update_user(user_id, {"state.selected_method_details": user_input, "state.step": 4})
                await show_payment_methods(update, context, user_id)

        elif state.get("flow") == "withdraw" and state.get("step") == 1:
            if not user_input.isdigit() or int(user_input) <= 0:
                await update.message.reply_text("Enter a valid positive integer for withdrawal amount.")
                return

            amount = int(user_input)

            total_balance = calculate_detailed_balance(user_id)["total_balance"]
            if amount > total_balance:
                await update.message.reply_text(
                    "Withdrawal amount exceeds your total balance. Enter a valid amount."
                )
                return

            update_user(user_id, {"state.amount": amount, "state.step": 2})
            await show_payment_methods(update, context, user_id)
    except Exception as e:
        await update.message.reply_text("An error occurred. Please try again later.")


class WebhookHandler(BaseHTTPRequestHandler):
    async def handle_webhook(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        update = Update.de_json(json.loads(post_data), Application.builder().token(TELEGRAM_TOKEN).build().bot)
        await Application.process_update(update)

    def do_POST(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.handle_webhook())
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"OK")


def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("restart", debug_restart))
    application.add_handler(CommandHandler("uptime", debug_uptime))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button))

    webhook_url = "https://gabriel-bernardo-portfolio.netlify.app/"
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8443)),
        url_path="webhook"
    )
    application.bot.setWebhook(webhook_url)

    server_address = ('', int(os.getenv("PORT", 8443)))
    httpd = HTTPServer(server_address, WebhookHandler)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
