# Slack API Client (`slack-api`)

This library provides a simple and reusable client for interacting with the Slack API. It is built using the `slack-bolt` for Python library, which simplifies the process of building Slack apps. This bot is designed to run using Socket Mode, allowing for real-time, interactive communication without needing a public-facing HTTP endpoint.

## Project Files

### `pyproject.toml`
* **Objective**: This file is the project definition file used by Poetry. It specifies project metadata, dependencies, and other configuration details.
* **Key Dependencies**:
    * `python-dotenv`: Used to load environment variables from a `.env` file, which is crucial for managing sensitive credentials like API tokens.
    * `slack-sdk`: The official Python SDK for the Slack Platform.
    * `slack-bolt`: A Python framework that makes it easy to build Slack apps with the latest platform features.

### `src/slack_api/__init__.py`
* **Objective**: This file makes the `slack_api` directory a Python package and exposes its main components for easier importing.
* **Functionality**: It imports the `SlackBot` class from the `messages` module, allowing users to import it directly with `from slack_api import SlackBot`.

### `src/slack_api/messages.py`
* **Objective**: This is the core file of the library, containing the `SlackBot` class which encapsulates all the logic for initializing and running the bot.
* **Class**: `SlackBot`
    * **`__init__(self, dotenv_path=None)`**
        * **Functionality**: The constructor initializes the Slack bot. It loads necessary environment variables (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`) from a `.env` file, creates an instance of the `slack_bolt.App`, and calls the internal `_register_events` method to set up event listeners.
        * **Inputs**:
            * `dotenv_path` (str, optional): The file path to the `.env` file. If not provided, it defaults to a hardcoded path.
        * **Outputs**: An instance of the `SlackBot` class.

    * **`_register_events(self)`**
        * **Functionality**: A private method responsible for registering all the bot's event handlers. It uses the `@self.app.event("message")` decorator to listen for any message posted in channels the bot is a part of. When a message event is received, it calls the `handle_message` method.
        * **Inputs**: None.
        * **Outputs**: None.

    * **`handle_message(self, message, say)`**
        * **Functionality**: This method defines the logic for how the bot responds to messages. It first checks that the message is not from another bot (`not message.get("bot_id")`) and is not a channel event like a user joining (`not message.get("subtype")`). If it's a valid user message, it echoes the message text back to the same channel, mentioning the user who sent it.
        * **Inputs**:
            * `message` (dict): The full event payload from the Slack API, containing details about the message and its sender.
            * `say` (function): A utility function provided by `slack-bolt` to easily send a message back to the originating channel.
        * **Outputs**: None. The function's effect is to send a message to a Slack channel.

    * **`start(self)`**
        * **Functionality**: This method starts the bot. It initializes a `SocketModeHandler`, which establishes a persistent WebSocket connection to Slack using the `SLACK_APP_TOKEN`. The `handler.start()` call is a blocking operation that listens for incoming events from Slack and dispatches them to the registered handlers.
        * **Inputs**: None.
        * **Outputs**: None. This function runs indefinitely until the process is stopped.

### `tests/slack_message.py`
* **Objective**: This file serves as a simple, standalone example of how to run a Slack bot using the `slack-bolt` library. It demonstrates the fundamental steps required to get a bot running.
* **Functionality**: The script loads environment variables, initializes a `slack-bolt` App, defines an event handler for messages (with the same logic as the `SlackBot` class), and starts the `SocketModeHandler` to connect to Slack. While it doesn't use the `SlackBot` class from this library, its code is a procedural equivalent and serves as a clear usage example.