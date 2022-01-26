import os
import logging
import re
import redis
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Updater, CommandHandler, ConversationHandler,
    MessageHandler, Filters, CallbackContext,
)
from random import choice
from dotenv import load_dotenv

logger = logging.getLogger("quiz_logger")

NEW_QUIZ, SURRENDER = range(2)


def start(update: Update, context: CallbackContext) -> int:

    quiz_keyboard = [
        ['Новый вопрос', 'Сдаться'],
        ['Мой счет']
    ]
    reply_markup = ReplyKeyboardMarkup(quiz_keyboard, resize_keyboard=True)
    update.message.reply_text(
        text='''Привет! Я бот для викторин.
Нажмите 'Новый вопрос' или команду /cancel для выхода''',
        reply_markup=reply_markup
    )

    return NEW_QUIZ


def cancel(update: Update, context: CallbackContext) -> int:

    user = update.message.from_user
    update.message.reply_text(
        text=f'До скорых встреч {user.first_name}!',
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def new_question_request(update: Update, context: CallbackContext) -> int:
    chat_id = update.message.chat['id']
    redis = context.bot_data['redis']

    quiz = choice(context.bot_data['quiz'])
    update.message.reply_text(quiz['Вопрос'])
    for key in redis.hkeys(chat_id):
        redis.hdel(chat_id, key)
    redis.hset(chat_id, mapping=quiz)

    return SURRENDER


def surrender(update: Update, context: CallbackContext) -> int:
    chat_id = update.message.chat['id']
    redis = context.bot_data['redis']
    quiz_from_db = redis.hgetall(chat_id)

    update.message.reply_text(quiz_from_db['Ответ'])
    if 'Комментарий' in quiz_from_db:
        update.message.reply_text(
            f'Комментарий: {quiz_from_db["Комментарий"]}'
        )

    return NEW_QUIZ


def solution_attempt(update: Update, context: CallbackContext) -> int:
    chat_id = update.message.chat['id']
    redis = context.bot_data['redis']
    quiz_from_db = redis.hgetall(chat_id)
    if not redis.get(f'{chat_id}:total'):
        redis.set(f'{chat_id}:total', '0')

    if quiz_from_db:
        if update.message.text.lower() == quiz_from_db['Ответ'].lower():
            update.message.reply_text(
                f'''Правильно! Поздравляю!
                Для следующего вопроса нажми «Новый вопрос»'''
            )
            redis.incr(f'{chat_id}:total')

            return NEW_QUIZ

        else:
            update.message.reply_text(
                f'Неправильно… Попробуешь ещё раз?'
            )

    return SURRENDER


def total_request(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat['id']
    redis = context.bot_data['redis']
    if not redis.get(f'{chat_id}:total'):
        redis.set(f'{chat_id}:total', '0')

    total = redis.get(f'{chat_id}:total')
    update.message.reply_text(f'Количество Ваших верных ответов: {total}')


def correct_quiz_text(quiz):
    corrected_quiz = quiz.copy()

    for quiz_element in corrected_quiz:
        for key, text in quiz_element.items():
            if key == 'Ответ':
                # удаляем все что внутри квадратных скобок
                quiz_element[key] = re.sub(r"\[([^\]]*)\]", '', text).strip()
                # удаляем символы \' \" \.
                quiz_element[key] = re.sub(r"[(^'\".)]", '', quiz_element[key])
            else:
                quiz_element[key] = text.replace('\n', ' ').strip()

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

    quiz = correct_quiz_text(quiz)

    return quiz


if __name__ == '__main__':

    logger.setLevel(logging.INFO)
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    logger.info('Запущен quiz_questions_bot')

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

    updater = Updater(token=bot_token)
    dispatcher = updater.dispatcher
    dispatcher.bot_data = {
        'redis': db_redis,
        'quiz': generate_quiz(2)
    }

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NEW_QUIZ: [MessageHandler(
                Filters.regex('^(Новый вопрос)$'), new_question_request),
                MessageHandler(Filters.regex('^(Мой счет)$'), total_request)
            ],

            SURRENDER: [
                MessageHandler(Filters.regex('^(Сдаться)$'), surrender),
                MessageHandler(Filters.regex('^(Мой счет)$'), total_request),
                MessageHandler(
                    Filters.text & ~Filters.command,
                    solution_attempt
                ),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(conv_handler)

    # dispatcher.add_handler(CommandHandler("start", start))
    # dispatcher.add_handler(CommandHandler("cancel", cancel))
    # dispatcher.add_handler(
    #     MessageHandler(
    #         Filters.text & ~Filters.command,
    #         processing_button_click)
    # )

    updater.start_polling()
    updater.idle()
