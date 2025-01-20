import os
import logging
import json
import requests
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)
from bot import write_email, send_email
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Replace with your predefined CV file path
PREDEFINED_CV_PATH = "cv.pdf"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize the Telegram bot application
application = Application.builder().token(BOT_TOKEN).build()

# States for ConversationHandler
EMAIL, JOB_DESCRIPTION, CHOOSE_CV, HANDLE_CV, REVIEW_EMAIL = range(5)

# Command to start the conversation
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Start command received")
    await update.message.reply_text("Please provide your email address:")
    return EMAIL

# Handle the email input
async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_email = update.message.text
    context.user_data['email'] = user_email
    await update.message.reply_text("Got it! Now, please provide the job description:")
    return JOB_DESCRIPTION

# Handle the job description input and generate the email
async def get_job_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job_description = update.message.text
    context.user_data['job_description'] = job_description

    # Write the email using Groq API
    subject, body = write_email(job_description, GROQ_KEY)
    context.user_data['email_subject'] = subject
    context.user_data['email_body'] = body

    # Display the email to the user
    await update.message.reply_text(f"Here is the email that will be sent:\n\nSubject: {subject}\n\nBody:\n{body}")

    # Ask the user if they want to send a CV
    keyboard = [
        [InlineKeyboardButton("Send Predefined CV", callback_data="predefined_cv")],
        [InlineKeyboardButton("Upload My CV", callback_data="upload_cv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Would you like to send a CV with this email?",
        reply_markup=reply_markup
    )
    return CHOOSE_CV

# Handle the user's choice of CV
async def choose_cv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query

    user_choice = query.data

    if user_choice == "predefined_cv":
        # Use the predefined CV
        context.user_data['cv_path'] = PREDEFINED_CV_PATH
        await query.edit_message_text("Using the predefined CV.")
        return REVIEW_EMAIL
    elif user_choice == "upload_cv":
        await query.edit_message_text("Please upload your CV as a PDF file.")
        return HANDLE_CV

# Handle the uploaded CV
async def handle_cv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document:
        file = await update.message.document.get_file()
        file_path = f"user_cv_{update.message.from_user.id}.pdf"
        await file.download_to_drive(file_path)
        context.user_data['cv_path'] = file_path
        await update.message.reply_text("CV received! Proceeding to send the email.")

        # Display the "Send" and "Don't Send" buttons
        keyboard = [
            [InlineKeyboardButton("Send", callback_data="send_email")],
            [InlineKeyboardButton("Don't Send", callback_data="dont_send")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Would you like to send this email?",
            reply_markup=reply_markup
        )
        return REVIEW_EMAIL
    else:
        await update.message.reply_text("Please upload a valid PDF file.")
        return HANDLE_CV

# Handle the user's decision to send or not send the email
async def review_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query:
        await query.answer()  # Acknowledge the callback query

    if query.data == "send_email":
        # Send the email with the CV attachment
        send_email(
            context.user_data['email'],
            SENDER_EMAIL,
            context.user_data['email_subject'],
            context.user_data['email_body'],
            context.user_data.get('cv_path')
        )
        await query.edit_message_text("Email sent successfully!")
    elif query.data == "dont_send":
        await query.edit_message_text("Email not sent.")

    return ConversationHandler.END

# Cancel command to end the conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.", reply_markup=None)
    return ConversationHandler.END

# Define the ConversationHandler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
        JOB_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_job_description)],
        CHOOSE_CV: [CallbackQueryHandler(choose_cv)],
        HANDLE_CV: [MessageHandler(filters.Document.ALL, handle_cv)],
        REVIEW_EMAIL: [CallbackQueryHandler(review_email)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,  # Explicitly set to False (or remove this line)
)

# Add the ConversationHandler to the application
application.add_handler(conv_handler)

# Flask route to handle incoming updates from Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    logger.info(json.dumps(data, indent=2))  # Log incoming data for debugging
    update = Update.de_json(data, application.bot)
    application.update_queue.put(update)
    return 'ok'

# Start the Flask app
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    application.run_polling()