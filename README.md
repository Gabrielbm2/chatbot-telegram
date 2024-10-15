# Telegram Chatbot

This is a Telegram bot developed to simulate functionalities of a FinTech platform, allowing users to perform operations such as checking balance, adding payment methods, and making deposits and withdrawals.

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Available Commands](#available-commands)

## Installation

To set up and run the project locally, follow the steps below:

1. **Clone the Repository**
    ```sh
    git clone git@github.com:Gabrielbm2/chatbot-telegram.git
    cd chatbot-telegram
    ```

2. **Configure Environment Variables**
   
   Create a `.env` file in the root of the project with the following content:
    ```env
    TELEGRAM_TOKEN=your_telegram_token
    ```

3. **Start Docker Compose**
    ```sh
    docker-compose up -d
    ```

## Configuration

Ensure that you have properly set the following environment variables:

- `TELEGRAM_TOKEN`: The API token of your Telegram Bot.
- The token is already pre-filled to facilitate the use of the Chatbot.

### Project Structure

- `app.py`: Main bot code, including user interaction logic and integration with Telegram.
- `database.py`: Contains functions to interact with MongoDB.
- `Dockerfile`: Instructions for creating the Docker image.
- `docker-compose.yml`: Docker Compose configuration for orchestrating services.


## Usage

After starting Docker, the bot will be running and ready to interact on Telegram. Use the `/start` command to start interacting with the bot.

## Available Commands

- `/start`: Initiates interaction with the bot and displays the main menu.
- `/debug_uptime`: Shows the bot's uptime.
- `/debug_restart`: Restarts the bot.

# Command to run the application
CMD ["python", "bot.py"]
