import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Load environment variables from .env file
load_dotenv()

# Initializes your app with your bot token
# The "App" class handles all the event processing
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.event("message")
def message_echo(message, say):
    """
    This function is called when a message is posted.
    
    'message': A dictionary containing the event's full payload.
    'say': A utility function to send a message back to the same channel.
    """
    if not message.get("bot_id") and not message.get("subtype"):
        user_message = message.get("text")
        say(
            text=f"<@{message['user']}>: {user_message}",
        )



# This is the main entry point of the application
if __name__ == "__main__":
    print("🤖 Bolt app is starting in Socket Mode...")
    # The SocketModeHandler connects your App to Slack's Socket Mode endpoints
    # It uses the SLACK_APP_TOKEN for the connection
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    
    # This starts the handler and waits for events
    handler.start()