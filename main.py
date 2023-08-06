import logging
import telegram
import psycopg2
import io
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from config import TELEGRAM_BOT_TOKEN, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from telegram import ParseMode
from contextlib import contextmanager
from PIL import Image

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

@contextmanager
def connect_to_db():
    connection = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    try:
        yield connection
    finally:
        connection.close()

def check_user_exists(user_id):
    with connect_to_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT EXISTS(SELECT 1 FROM user_coins WHERE user_id = %s)", (user_id,))
        return cursor.fetchone()[0]
    return False

def get_video_info(video_id):
    with connect_to_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT title, description, time, price, image, url FROM videos WHERE id = %s", (video_id,))
        video_info = cursor.fetchone()
        return video_info
    
def compress_image(image_path, max_size=1024, quality=40):
    img = Image.open(image_path)
    img.thumbnail((max_size, max_size))
    buffered = io.BytesIO()
    img.save(buffered, format="WebP", quality=quality)
    return buffered.getvalue()
    
def create_user_record(user_id):
    print("Creating user record for create_user_record:", user_id)
    with connect_to_db() as connection:
        cursor = connection.cursor()

        # Insert user ID and initial coins into the user_coins table
        initial_coins = 0  # Change this to set the initial coins for new users
        cursor.execute("INSERT INTO user_coins (user_id, coins, invited_count) VALUES (%s, %s, 0) ON CONFLICT DO NOTHING", (user_id, initial_coins))
        connection.commit()  # Add an explicit commit here

def save_referral(inviter_id, new_user_id):
    print("Saving referral for inviter:", inviter_id, "and new user:", new_user_id)
    with connect_to_db() as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO referrals (inviter_id, new_user_id) VALUES (%s, %s)", (inviter_id, new_user_id))
        connection.commit()

        # Increment the invited_count for the inviter
        cursor.execute("UPDATE user_coins SET invited_count = invited_count + 1 WHERE user_id = %s", (inviter_id,))
        connection.commit()

def get_user_coins(user_id):
    print("getting coins for user:", user_id)
    with connect_to_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT coins FROM user_coins WHERE user_id = %s", (user_id,))
        coins_record = cursor.fetchone()
        return coins_record[0] if coins_record else 0
        
def update_user_coins(user_id, new_coins):
    print("Updating coins for user:", user_id)
    # Connect to the PostgreSQL database
    with connect_to_db() as connection:
        cursor = connection.cursor()

        # Update the user's coins in the user_coins table
        cursor.execute("UPDATE user_coins SET coins = %s WHERE user_id = %s", (new_coins, user_id))
        connection.commit()
    pass
    
def get_video_titles():
    print("get video titles:")
    with connect_to_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT title FROM videos WHERE id BETWEEN 1 AND 8 ORDER BY id")
        video_titles = [row[0] for row in cursor.fetchall()]
        return video_titles

def send_menu(chat_id, user_id, user_name):
    # Fetch user's coin count
    #create_user_record(user_id)
    user_coins = get_user_coins(user_id)

    # Compose the message with video details and buttons using Markdown formatting
    video_titles = get_video_titles()
    video_buttons = []
    emoji = "🕶️"
    for i in range(0, len(video_titles), 2):
        button1 = InlineKeyboardButton(f"{emoji} {video_titles[i]}", callback_data=f"video_{i + 1}")
        button2 = InlineKeyboardButton(f"{emoji} {video_titles[i + 1]}", callback_data=f"video_{i + 2}")
        video_buttons.append([button1, button2])
    referral_link = generate_referral_link(user_id)
    invite_button = InlineKeyboardButton("🎉 Invite Friend To Get Free Coins 🎉", callback_data="invite_callback")
    video_buttons.append([invite_button])
    recharge_button = InlineKeyboardButton("💰 Recharge Coins 💰", callback_data="recharge")
    video_buttons.append([recharge_button])
    reply_markup = InlineKeyboardMarkup(video_buttons)

    welcome_message = (
        f"🎉🎉 *Welcome, {user_name}!* 🎉🎉\n"
        f"_Your user ID is: {user_id}_\n\n"
        f"💰 You have *{user_coins} coins* 💰\n\n"
        "*Select the video you want to watch:*"
    )

    # Send the welcome message with photo, video details, and buttons
    welcome_image_path = "image/ht.jpg"  # Replace with the actual path to the image
    compressed_image_data = compress_image(welcome_image_path)
    bot.send_photo(
        chat_id=chat_id,
        photo=io.BytesIO(compressed_image_data),
        caption=welcome_message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    pass
    
def generate_referral_link(user_id):
    bot_username = bot.get_me().username
    # In this example, we will use a simple format to generate the referral link
    # You can use any format or hashing algorithm that suits your needs
    # For simplicity, we will use the user's Telegram user ID as the referral parameter
    referral_link = f"https://t.me/{bot_username}?start=invite_{user_id}"  # Replace "YourBotUsername" with your actual bot's username
    return referral_link
    
def send_invite_message(chat_id, referral_link, invited_count):
    message = (
        "🎉 *Invite Friends and Get Free Coins!* 🎉\n\n"
        "Invite your friends to join using this link:\n"
        f"`{referral_link}`\n\n"  # Enclose the referral_link in backticks to avoid Markdown formatting issues
        f"You have invited {invited_count} friends so far.\n"
        "For every 5 friends who join, you'll get 1 free coin!"
    )
    back_to_menu_button = InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")
    reply_markup = InlineKeyboardMarkup([[back_to_menu_button]])
    # Send the invite message to the user
    bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

    
def invite_friend(update, context):
    referral_link = update.message.text
    user_id_str = referral_link.split("invite_")[1] if "invite_" in referral_link else None

    new_user_id = update.message.from_user.id
    inviter_id = int(user_id_str) if user_id_str else None
    user_name = update.message.from_user.first_name

    # Create user records for new users and the inviter (if available)
    create_user_record(new_user_id)
    print("tách")
    #if inviter_id:
        #create_user_record(inviter_id)

    # Save the referral information in the database
    if inviter_id and inviter_id != new_user_id:
        save_referral(inviter_id, new_user_id)

    # Reset the invited count if needed
    if inviter_id:
        reset_invited_count_if_needed(inviter_id, new_user_id)

    # Display the main menu to the new user
    send_menu(update.message.chat_id, new_user_id, user_name)
    context.user_data["state"] = "menu"


def reset_invited_count_if_needed(inviter_id, new_user_id):
    # Get the current invited_count for the inviter
    current_invited_count = get_invited_count(inviter_id)

    # Check if the inviter has invited more than 5 users
    if current_invited_count >= 5:
        # Reset the invited_count to 0
        reset_invited_count(inviter_id)

        # Grant 1 coin as a reward to the inviter
        grant_inviter_reward(inviter_id)

        # Update the invited_count for the new user (new_user_id) to 0
        reset_invited_count(new_user_id)

def get_invited_count(user_id):
    print("get invited count", user_id)
    with connect_to_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT invited_count FROM user_coins WHERE user_id = %s", (user_id,))
        invited_count_record = cursor.fetchone()
        return invited_count_record[0] if invited_count_record else 0

def reset_invited_count(user_id):
    print("reset invited count ", user_id)
    # Connect to the PostgreSQL database
    with connect_to_db() as connection:
        cursor = connection.cursor()

        # Reset the invited_count to 0
        cursor.execute("UPDATE user_coins SET invited_count = 0 WHERE user_id = %s", (user_id,))
        connection.commit()

def grant_inviter_reward(inviter_id):
    print("grant coin to invite > 5:", inviter_id)
    # Connect to the PostgreSQL database
    with connect_to_db() as connection:
        cursor = connection.cursor()

        # Get the current coins for the inviter
        current_coins = get_user_coins(inviter_id)

        # Grant 1 coin as a reward to the inviter
        new_coins = current_coins + 1

        # Update the coins in the user_coins table
        cursor.execute("UPDATE user_coins SET coins = %s WHERE user_id = %s", (new_coins, inviter_id))
        connection.commit()
    pass

def get_invite(update, context):
    user_id = update.message.from_user.id

    # Get the referral link from the message text
    referral_link = update.message.text
    
    # Check if the referral link is valid
    if referral_link.startswith("https://t.me/Test_banvideo_bot?start=invite_"):
        # Extract the inviter's user ID from the referral link
        inviter_user_id = int(referral_link.split("invite_")[1])

        # Check if the inviter's user ID exists in the database (optional)
        # For simplicity, we assume you have a function named "check_user_exists" to check if a user exists in the database
        if check_user_exists(inviter_user_id):
            # Grant coins to the inviter as a reward (optional)
            # For simplicity, we assume you have a function named "grant_referral_reward" to handle this task
            # You may need to adjust this function based on your database schema and requirements
            grant_referral_reward(inviter_user_id, user_id)

    # Display the main menu to the new user
    send_menu(update.message.chat_id, user_id, update.message.from_user.first_name)
    context.user_data["state"] = "menu"

def start(update, context):
    #create_user_record(user_id)
    context.user_data.setdefault("state", "menu")
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    # Check if the user's state is "menu" (indicating they are on the main menu)
    if context.user_data.get("state") == "menu":
        # Call the create_user_record function to insert the user into the database if they don't exist
        if not check_user_exists(user_id):
            # If the user is new, generate and display the referral link
            invite_friend(update, context)
            # Set the user's state to "menu"
            context.user_data["state"] = "menu"
        else:
            # If the user is not new, simply display the main menu
            send_menu(update.message.chat_id, user_id, user_name)
            # Set the user's state to "menu"
            context.user_data["state"] = "menu"

    elif context.user_data.get("state") == "video":
        # If the user's state is "video" (indicating they are viewing a video), do nothing for now.
        # You can add any additional handling here if needed.
        pass

def has_user_purchased_video(user_id, video_id):
    print("check purchased video", user_id)
    with connect_to_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT EXISTS(SELECT 1 FROM purchased_videos WHERE user_id = %s AND video_id = %s)", (user_id, video_id))
        return cursor.fetchone()[0]

def video_button(update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        query_data = query.data
        logging.info(f"Button pressed. User ID: {user_id}, Query data: {query_data}")
        if query_data == "invite_callback":
            
            referral_link = generate_referral_link(user_id)
            inviter_invited_count = get_invited_count(user_id)
            send_invite_message(query.message.chat.id, referral_link, inviter_invited_count)  # Pass the invited_count
            print("tách")
            # Check if the inviter has invited more than 5 users to reset the count
            reset_invited_count_if_needed(user_id, user_id)


        # Handle the "Back to Menu" button and other video-related buttons separately (as before)
        elif query_data == "back_to_menu":
            # Fetch user's coin count
            send_menu(query.message.chat_id, user_id, query.from_user.first_name)
            return

        else:
            video_id = int(query_data.split("_")[1])
            video_info = get_video_info(video_id)

            if video_info:
                video_title, description, time, price, image, url = video_info

                # Compress the image
                compressed_image_data = compress_image(image)

                # Compose the message with video details and buttons using Markdown formatting
                message = (
                    f"*{video_title}*\n"
                    f"_{description}_\n"
                    f"*Time: {time}*\n"
                    f"*Price: {price} coins*"
                )

                if query_data.startswith("open_"):
                    # Check if the user has already purchased the video
                    if has_user_purchased_video(user_id, video_id):
                        # If the user has already purchased the video, display a message
                        bot.send_message(chat_id=query.message.chat.id, text=f"You have already purchased {video_title}. You can watch it again without any additional coins!")
                        back_to_menu_button = InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")
                        reply_markup = InlineKeyboardMarkup([[back_to_menu_button]])
                        bot.send_message(chat_id=query.message.chat.id, text=f"Here's the video link: {url}", reply_markup=reply_markup)
                        return
                    else:
                        # Check if the user has enough coins to watch the video
                        user_coins = get_user_coins(user_id)
                        if user_coins >= price:
                            # Deduct the price from the user's coins in the database
                            new_coins = user_coins - price
                            update_user_coins(user_id, new_coins)

                            # Add the video_id to the purchased_videos table to mark it as purchased
                            add_purchased_video(user_id, video_id)

                            if url:
                                # Send a message indicating successful purchase and provide the video URL to watch
                                bot.send_message(chat_id=query.message.chat.id, text=f"You have purchased {video_title}. Enjoy the video!")
                                context.user_data["state"] = "video"
                                back_to_menu_button = InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")
                                reply_markup = InlineKeyboardMarkup([[back_to_menu_button]])
                                bot.send_message(chat_id=query.message.chat.id, text=f"Here's the video link: {url}", reply_markup=reply_markup)
                                context.user_data["state"] = "menu"
                                return
                                # Add code here to open the video or take any further actions
                                # ...

                            else:
                                # If the URL is not found in the database, handle the error
                                bot.send_message(chat_id=query.message.chat.id, text="Video URL not found. Please contact the administrator.")
                        else:
                            # Notify the user if they don't have enough coins to watch the video
                            bot.send_message(chat_id=query.message.chat.id, text="🚫 *You don't have enough coins to watch this video. Please recharge your coins.* 🚫")

                # Create buttons for recharging coins and going back to the menu
                recharge_button = InlineKeyboardButton("Recharge Coins", callback_data="recharge")
                back_to_menu_button = InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")

                # Check if the video is purchased and update the button text accordingly
                open_button_text = f"Purchased." if has_user_purchased_video(user_id, video_id) else f"Open Video with ({price} coins)"
                open_button = InlineKeyboardButton(open_button_text, callback_data=f"open_{video_id}")

                reply_markup = InlineKeyboardMarkup([[open_button, recharge_button], [back_to_menu_button]])

                # Send the message with photo, video details, and buttons
                bot.send_photo(
                    chat_id=query.message.chat.id,
                    photo=io.BytesIO(compressed_image_data),
                    caption=message,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            else:
                bot.send_message(chat_id=query.message.chat.id, text="Invalid video ID.")

    except Exception as e:
        logging.error(f"Error in video_button: {e}")
        back_to_menu_button = InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")
        reply_markup = InlineKeyboardMarkup([[back_to_menu_button]])
        bot.send_message(chat_id=update.effective_chat.id, text="Exciting updates coming soon! Stay tuned! 🚀", reply_markup=reply_markup)    
        
def add_purchased_video(user_id, video_id):
    print("add_purchased_video:", user_id)
    # Connect to the PostgreSQL database
    with connect_to_db() as connection:
        cursor = connection.cursor()

        try:
            # Create the query string with placeholders
            query = "INSERT INTO purchased_videos (user_id, video_id) VALUES (%s, %s)"
            # Create a tuple of parameters with the actual values
            params = (user_id, video_id)

            # Print the formatted query with actual values
            formatted_query = cursor.mogrify(query, params)

            # Insert the user_id and video_id into the purchased_videos table
            cursor.execute(query, params)
            connection.commit()
            logging.info(f"Video purchase record added successfully. User ID: {user_id}, Video ID: {video_id}")
        except Exception as e:
            connection.rollback()  # Rollback the changes in case of an error
            logging.error(f"Error in add_purchased_video: {e}")
            raise e  # Re-raise the exception to propagate it further if needed


if __name__ == '__main__':
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(video_button))
    updater.start_polling()
    updater.idle()
