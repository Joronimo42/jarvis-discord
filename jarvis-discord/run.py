import os
import json
import time
import requests
import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands

# --- Configuration ---
# Load configuration from environment variables.
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable not set.")

# The channel ID where the bot should listen (set to 0 or leave empty to allow all channels)
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
if DISCORD_CHANNEL_ID:
    DISCORD_CHANNEL_ID = int(DISCORD_CHANNEL_ID)

HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL")
if not HOME_ASSISTANT_URL:
    raise ValueError("HOME_ASSISTANT_URL environment variable not set.")

# Optional Home Assistant long-lived access token for authorization.
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")

# The agent id to send (defaulting to "ollama" if not specified)
AGENT_ID = os.getenv("AGENT_ID", "ollama")

# Load the user mapping; expected as a JSON string in the environment variable.
USER_MAPPING = {}
user_mapping_env = os.getenv("USER_MAPPING")
if user_mapping_env:
    try:
        USER_MAPPING = json.loads(user_mapping_env)
    except Exception as e:
        print("Error loading USER_MAPPING from environment:", e)
        USER_MAPPING = {}

# --- Conversation Context Management ---
# This class manages a shared conversation context that resets after 1 hour of inactivity.
class ConversationContext:
    def __init__(self):
        self.conversation_id = None
        self.last_active = None

    def update(self):
        now = datetime.utcnow()
        # Reset conversation if last activity was over 1 hour ago.
        if self.last_active is None or (now - self.last_active) > timedelta(hours=1):
            self.conversation_id = f"discord-{int(now.timestamp())}"
        self.last_active = now
        return self.conversation_id

conv_context = ConversationContext()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
# Enable reading message content (required for command processing)
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

# Main message event – process messages that start with "!".
@bot.event
async def on_message(message):
    # Ignore messages from the bot itself.
    if message.author == bot.user:
        return

    # If a specific channel is set, ignore messages from other channels.
    if DISCORD_CHANNEL_ID and message.channel.id != DISCORD_CHANNEL_ID:
        return

    # Process only messages that start with the command prefix "!".
    if not message.content.startswith("!"):
        return

    # Remove the prefix and trim whitespace.
    command_text = message.content[1:].strip()

    # Update (or reset) the conversation context.
    conversation_id = conv_context.update()

    # Build the payload to send to Home Assistant.
    payload = {
        "text": command_text,
        "agent_id": AGENT_ID,
        "conversation_id": conversation_id,
    }

    # If the author is mapped to a Home Assistant person, include that info.
    discord_user_id = str(message.author.id)
    if discord_user_id in USER_MAPPING:
        payload["conversation_speaker"] = {"id": USER_MAPPING[discord_user_id]}

    # Prepare headers (include authorization if a token is provided).
    headers = {"Content-Type": "application/json"}
    if HOME_ASSISTANT_TOKEN:
        headers["Authorization"] = f"Bearer {HOME_ASSISTANT_TOKEN}"

    # Send the request to Home Assistant's conversation API.
    try:
        response = requests.post(HOME_ASSISTANT_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        # Assume Home Assistant returns a JSON with a key "response"
        reply_text = data.get("response", "No response from Home Assistant.")
    except Exception as e:
        reply_text = f"Error communicating with Home Assistant: {e}"

    # Prepend the user's display name if mapped.
    user_display = message.author.display_name
    if discord_user_id in USER_MAPPING:
        reply_text = f"{user_display}, {reply_text}"

    await message.channel.send(reply_text)

    # Allow commands to be processed if any other commands are added later.
    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
