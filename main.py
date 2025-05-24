import logging
import google.generativeai as genai
import os
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters
from keep_alive import keep_alive
from chat_logger import ChatLogger
from datetime import datetime

# Load your API keys securely from environment variables
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))  # Admin user ID
ALLOWED_USERS = set(int(id) for id in os.environ.get('ALLOWED_USERS', '').split(',') if id)
ASSISTANT_ACTIVE = True  # Global variable to control assistant state

if not TELEGRAM_TOKEN or not GEMINI_API_KEY or not ADMIN_ID:
    raise ValueError("Please set TELEGRAM_TOKEN, GEMINI_API_KEY and ADMIN_ID environment variables")

genai.configure(api_key=GEMINI_API_KEY)

# Enable logging
logging.basicConfig(level=logging.INFO)

# Initialize Pyrogram bot client
API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')

if not API_ID or not API_HASH:
    raise ValueError("Please set API_ID and API_HASH environment variables")

# Initialize chat logger
chat_logger = ChatLogger()

app = Client(
    "telegram-ai-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=TELEGRAM_TOKEN
)

# Assistant control commands
@app.on_message(filters.command(["on", "sa"]) & filters.private)
async def start_assistant(client, message):
    global ASSISTANT_ACTIVE
    chat_id = message.chat.id
    ASSISTANT_ACTIVE = True
    await message.reply("🟢 **Gemini responses are now enabled!**", parse_mode="html")

@app.on_message(filters.command(["off", "ss"]) & filters.private)
async def stop_assistant(client, message):
    global ASSISTANT_ACTIVE
    chat_id = message.chat.id
    ASSISTANT_ACTIVE = False
    await message.reply("🔴 **Gemini responses are now disabled. You can still use commands like /sum!**", parse_mode="html")

# Get Gemini response for text
def get_gemini_response(prompt: str) -> str:
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

# Get Gemini response for images
async def get_gemini_vision_response(image_path: str, prompt: str = "") -> str:
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        with open(image_path, 'rb') as img_file:
            image_data = img_file.read()

        default_prompt = """
        Please analyze this image in a beginner-friendly way:
        1. If it's a math problem:
           - First, explain what type of problem it is
           - Break down the solution into very simple steps
           - Explain each step like you're teaching a beginner
           - Show the final answer clearly

        2. If it's any other image:
           - Describe what you see in simple terms
           - Explain any important details
           - Use simple language that anyone can understand

        Make sure to use clear explanations and avoid complex terms without explanation.
        """

        response = model.generate_content([
            prompt or default_prompt,
            {"mime_type": "image/jpeg", "data": image_data}
        ])

        # Make the response more readable with formatting
        formatted_response = (
            "🔍 Analysis:\n\n" + 
            response.text.replace("Step ", "\n📝 Step ").replace(". ", ".\n")
        )

        return formatted_response, None  # No visualization for now
    except Exception as e:
        return f"Error analyzing image: {str(e)}", None

# Handle logs command
@app.on_message(filters.command("logs") & filters.private)
async def view_logs(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("You are not authorized to view logs.")
        return

    try:
        # Get date from command or use today's date
        args = message.text.split()
        if len(args) > 1:
            date = datetime.strptime(args[1], "%Y-%m-%d").strftime("%Y-%m-%d")
        else:
            date = datetime.now().strftime("%Y-%m-%d")

        log_file = os.path.join("chat_logs", f"chat_log_{date}.txt")

        if not os.path.exists(log_file):
            await message.reply(f"No logs found for date {date}")
            return

        with open(log_file, "r", encoding="utf-8") as f:
            logs = f.read()

        # Split logs into chunks if too long
        max_length = 4000  # Telegram message length limit
        if len(logs) > max_length:
            chunks = [logs[i:i + max_length] for i in range(0, len(logs), max_length)]
            for chunk in chunks:
                await message.reply(chunk)
        else:
            await message.reply(logs or "No messages found.")

    except Exception as e:
        await message.reply(f"Error reading logs. Usage: /logs YYYY-MM-DD\nExample: /logs 2024-05-23")

# Handle backup command
@app.on_message(filters.command("backup") & filters.private)
async def backup_chats(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("You are not authorized to use the backup command.")
        return

    try:
        # Parse time range from command
        time_range = message.text.replace("/backup", "").strip()
        start_str, end_str = [t.strip() for t in time_range.split("-")]

        # Convert time strings to datetime objects
        start_time = datetime.strptime(start_str, "%I:%M%p").replace(
            year=datetime.now().year,
            month=datetime.now().month,
            day=datetime.now().day
        )
        end_time = datetime.strptime(end_str, "%I:%M%p").replace(
            year=datetime.now().year,
            month=datetime.now().month,
            day=datetime.now().day
        )

        # Get chat history
        chat_history = chat_logger.get_chat_history(start_time, end_time)

        # Format backup message
        backup_text = "📑 Chat Backup Report\n\n"
        for entry in chat_history:
            backup_text += f"{entry}\n"

        await message.reply(backup_text or "No chat history found for the specified time range.")

    except Exception as e:
        logging.error(f"Error creating backup: {str(e)}")
        await message.reply("Please use the format: /backup 1:00pm - 2:00pm")

# Handle YouTube summarization command
@app.on_message(filters.command("sum") & filters.private)
async def summarize_youtube(client, message):
    try:
        # Extract YouTube URL from message
        args = message.text.split()
        if len(args) != 2:
            await message.reply("Please provide a YouTube URL.\nFormat: /sum youtube_url")
            return

        url = args[1]
        if "youtube.com" not in url and "youtu.be" not in url:
            await message.reply("Please provide a valid YouTube URL")
            return

        # Extract video ID
        if "youtu.be" in url:
            video_id = url.split("/")[-1]
        else:
            video_id = url.split("v=")[-1].split("&")[0]

        from youtube_transcript_api import YouTubeTranscriptApi

        # Get video transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([t['text'] for t in transcript_list])

        # Generate summary using Gemini
        prompt = f"""Please provide a concise summary of this YouTube video transcript. Format the response with:
        - Key points in bullet points
        - Important quotes or highlights
        - Main takeaways
        \n\n{transcript_text}"""
        summary = get_gemini_response(prompt)

        formatted_response = (
            "🎥 *YouTube Video Summary* 🎬\n\n"
            f"📌 *Key Points*:\n{summary}\n\n"
            "💡 *Generated by AI Assistant* ✨"
        )

        await message.reply(formatted_response, parse_mode="Markdown")

    except Exception as e:
        await message.reply(f"Error summarizing video: {str(e)}\nMake sure the video has English subtitles available.")



# Handle promotion command
@app.on_message(filters.command("promote") & filters.private)
async def promote_user(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("You are not authorized to promote users.")
        return

    try:
        user_id = int(message.text.split()[1])
        ALLOWED_USERS.add(user_id)
        await message.reply(f"User {user_id} has been granted access to the bot.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid user ID.\nFormat: /promote user_id")

# Handle start command
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    welcome_text = (
        "🌟 **Welcome to AI Assistant Bot!** 🤖\n\n"
        "I'm here to help you with:\n"
        "📸 **Image Analysis**\n"
        "🎥 **YouTube Summaries** (/sum)\n"
        "💬 **Chat Assistance**\n"
        "🔍 **Document Analysis**\n\n"
        "Feel free to send me messages, images, or YouTube links! 🚀\n"
        "💡 __Powered by Gemini AI__"
    )
    
    try:
        # Send text-only welcome message
        await message.reply(
            welcome_text,
            parse_mode="markdown"  # lowercase is correct
        )
    except Exception as e:
        logging.error(f"Error in start command: {str(e)}")
        await message.reply("👋 Welcome! I'm your AI Assistant Bot ready to help!")

# Handle messages
@app.on_message(filters.private & (filters.text | filters.photo))
async def handle_message(client, message):
    # Allow commands to work even when assistant is inactive
    if message.text and message.text.startswith('/'):
        return  # Let other command handlers process this

    try:
        if not ASSISTANT_ACTIVE:
            return
        if message.photo:
            # Handle image message
            logging.info("Received image message")
            photo = message.photo.file_id

            # Ensure downloads directory exists
            os.makedirs("downloads", exist_ok=True)
            download_path = f"downloads/temp_{message.id}.jpg"

            # Download the photo
            await message.download(download_path)
            caption = message.caption if message.caption else ""
            reply_text, visualization = await get_gemini_vision_response(download_path, caption)

            # Send the text response
            await message.reply(reply_text)

            # Send visualization if available
            if visualization:
                viz_path = f"downloads/viz_{message.id}.png"
                with open(viz_path, 'wb') as f:
                    f.write(visualization)
                await message.reply_photo(viz_path)
                os.remove(viz_path)

            # Clean up the temporary file
            if os.path.exists(download_path):
                os.remove(download_path)

            # Log messages
            chat_logger.save_message(message.from_user.id, "Image Message")
            chat_logger.save_message(message.from_user.id, reply_text, is_bot_response=True)
        else:
            # Handle text message
            logging.info(f"Received text message: {message.text}")
            reply_text = get_gemini_response(message.text)
            logging.info(f"Generated response: {reply_text}")

            # Log messages
            chat_logger.save_message(message.from_user.id, message.text)
            chat_logger.save_message(message.from_user.id, reply_text, is_bot_response=True)

            await message.reply(reply_text)

    except Exception as e:
        logging.error(f"Error handling message: {str(e)}")
        await message.reply("Sorry, I encountered an error processing your message.")

# Daily news report function
async def send_daily_news():
    while True:
        now = datetime.now()
        # Set time for 9:00 PM
        scheduled_time = now.replace(hour=21, minute=0, second=0, microsecond=0)
        
        # If it's past today's time, schedule for tomorrow
        if now >= scheduled_time:
            scheduled_time += timedelta(days=1)
            
        # Wait until scheduled time
        wait_seconds = (scheduled_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        try:
            # Generate news report using Gemini
            prompt = """Generate a comprehensive daily news report covering:
            1. Latest technological inventions and innovations
            2. Global football news and match results
            3. Cricket updates and match summaries
            4. Major global conflict updates
            
            Format with emojis and clear sections. Keep it concise but informative."""
            
            news_report = get_gemini_response(prompt)
            formatted_report = f"📰 *Daily News Report* 📰\n\n{news_report}\n\n🕘 Generated at {now.strftime('%Y-%m-%d %I:%M %p')}"
            
            # Send to all users in ALLOWED_USERS
            for user_id in ALLOWED_USERS:
                try:
                    await app.send_message(user_id, formatted_report, parse_mode="Markdown")
                except Exception as e:
                    logging.error(f"Failed to send report to user {user_id}: {str(e)}")
                    
        except Exception as e:
            logging.error(f"Error generating daily report: {str(e)}")

# Start the bot
if __name__ == "__main__":
    keep_alive()
    # Add asyncio event loop for daily news
    loop = asyncio.get_event_loop()
    loop.create_task(send_daily_news())
    app.run()