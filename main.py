import openai
import logging
import os

from dotenv import load_dotenv

from db import get_db_connection

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor

logging.basicConfig(level=logging.INFO)

load_dotenv()

TOKEN = os.getenv("TOKEN")
openai.api_key = os.getenv("API_KEY")

bot = Bot(TOKEN)
dp = Dispatcher(bot)

try:
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa (
                id SERIAL PRIMARY KEY,
                question TEXT UNIQUE,
                answer TEXT
            );
        """)
        connection.commit()
finally:
    if connection:
        connection.close()

@dp.message_handler()
async def send_message(message: types.Message):
    question = message.text.lower()
    
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT answer FROM qa WHERE question = %s", (question,))
            result = cursor.fetchone()
        
        if result:
            answer = result[0]
            logging.info("Answer found in database: %s", answer)
            await message.reply(answer)
        else:
            thinking_message = await message.reply("_Думаю..._", parse_mode="Markdown")
            
            response = openai.ChatCompletion.create(
                model='gpt-3.5-turbo',
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": question}
                ],
                temperature=0.9,
                max_tokens=1000,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.6
            )
            answer = response['choices'][0]['message']['content']
            logging.info("Generated answer from AI model: %s", answer)
            
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO qa (question, answer) VALUES (%s, %s) ON CONFLICT (question) DO NOTHING",
                    (question, answer)
                )
                connection.commit()

            await thinking_message.edit_text(answer)
    except Exception as ex:
        logging.error("Error occurred while processing request: %s", ex)
        await message.reply("Нажаль, сталася помилка під час виконання запиту. Спробуйте ще раз пізніше.")
    finally:
        if connection:
            connection.close()

executor.start_polling(dp, skip_updates=True)
