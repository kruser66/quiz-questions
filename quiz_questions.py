import os
import logging
import redis
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler,
    MessageHandler, Filters, CallbackContext,
)
from random import choice
from dotenv import load_dotenv

logger = logging.getLogger("quiz_logger")


def start(update: Update, context: CallbackContext) -> None:

    quiz_keyboard = [
        ['Новый вопрос', 'Сдаться'],
        ['Мой счет']
    ]
    reply_markup = ReplyKeyboardMarkup(quiz_keyboard, resize_keyboard=True)
    update.message.reply_text(
        text="Привет! Я бот для викторин.",
        reply_markup=reply_markup
    )


def processing_button_click(update: Update, context: CallbackContext) -> None:
    button = update.message.text
    chat_id = update.message.chat['id']
    redis = context.bot_data['redis']
    quiz_from_db = redis.hgetall(chat_id)
    if not redis.get(f'{chat_id}:total'):
        redis.set(f'{chat_id}:total', '0')

    if button == 'Новый вопрос':
        quiz = choice(context.bot_data['quiz'])
        update.message.reply_text(quiz['Вопрос'])
        for key in redis.hkeys(chat_id):
            redis.hdel(chat_id, key)
        redis.hset(chat_id, mapping=quiz)

    elif button == 'Сдаться':
        update.message.reply_text(quiz_from_db['Ответ'])
        if 'Комментарий' in quiz_from_db:
            update.message.reply_text(
                f'Комментарий: {quiz_from_db["Комментарий"]}'
            )

    elif button == 'Мой счет':
        total = redis.get(f'{chat_id}:total')
        update.message.reply_text(f'Количество Ваших верных ответов: {total}')

    else:
        if quiz_from_db:
            if button.lower() == quiz_from_db['Ответ'].lower():
                update.message.reply_text(
                    f'''Правильно! Поздравляю!
                    Для следующего вопроса нажми «Новый вопрос»'''
                )
                redis.incr(f'{chat_id}:total')
            else:
                update.message.reply_text(
                    f'Неправильно… Попробуешь ещё раз?'
                )


def correct_text_quiz(quiz):
    corrected_quiz = quiz.copy()
    for element in corrected_quiz:
        element['Вопрос'] = element['Вопрос'].replace('\n', ' ').lstrip()
        element['Ответ'] = element['Ответ'].replace('"', '')
        element['Ответ'] = element['Ответ'].replace("'", '')
        element['Ответ'] = element['Ответ'].replace(".", '')
        if 'Комментарий' in element:
            element['Комментарий'] = element['Комментарий'].replace('\n', ' ').lstrip()

    return corrected_quiz


def generate_quiz(count=5):
    starts = [
        'Ответ', 'Комментарий'
    ]
    quiz = []
    for _ in range(count):
        filename = os.path.join('files', choice(os.listdir('files')))
        logger.info(filename)
        with open(filename, 'r', encoding='KOI8-R') as file:
            content = file.read()

        quiz_element = {}

        for line in content.split('\n\n'):
            if line.startswith('Вопрос'):
                if quiz_element:
                    quiz.append(quiz_element)
                quiz_element = {}
                quiz_element.update({'Вопрос': line.split(':\n')[1]})

            elif line.split(':')[0] in starts:
                element = line.split(':')[0]
                quiz_element.update({element: line.split(':\n')[1]})

        if quiz_element:
            quiz.append(quiz_element)

    quiz = correct_text_quiz(quiz)

    return quiz


if __name__ == '__main__':

    load_dotenv()
    bot_token = os.environ['TG_BOT_TOKEN']

    redis_host = os.environ['DB_REDIS']
    redis_port = os.environ['DB_PORT']
    redis_password = os.environ['DB_PASSWORD']

    db_redis = redis.StrictRedis(
        host=redis_host,
        port=redis_port,
        password=redis_password,
        charset="utf-8",
        decode_responses=True
    )

    logger.setLevel(logging.INFO)
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    logger.info('Запущен quiz_questions_bot')

    updater = Updater(token=bot_token)
    dispatcher = updater.dispatcher
    dispatcher.bot_data = {
        'redis': db_redis,
        'quiz': generate_quiz(3)
    }

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(
        MessageHandler(
            Filters.text & ~Filters.command,
            processing_button_click)
    )

    updater.start_polling()
    updater.idle()
