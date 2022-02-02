import os
import logging
import redis
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Updater, CommandHandler, ConversationHandler,
    MessageHandler, Filters, CallbackContext,
)
from random import choice
from dotenv import load_dotenv
from quiz_maker import generate_quiz

logger = logging.getLogger("quiz_logger")

NEW_QUIZ, SURRENDER = range(2)


def start(update: Update, context: CallbackContext) -> int:

    quiz_keyboard = [
        ['Новый вопрос', 'Сдаться'],
        ['Мой счет']
    ]
    reply_markup = ReplyKeyboardMarkup(quiz_keyboard, resize_keyboard=True)
    update.message.reply_text(
        text='''Привет!
        Я бот - викторина.
        Нажмите "Новый вопрос"" или команду /cancel для выхода''',
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
    current_quiz = redis.hgetall(chat_id)

    update.message.reply_text(f'Ответ: {current_quiz["Ответ"]}')
    if 'Комментарий' in current_quiz:
        update.message.reply_text(
            f'Комментарий: {current_quiz["Комментарий"]}'
        )

    return NEW_QUIZ


def solution_attempt(update: Update, context: CallbackContext) -> int:
    chat_id = update.message.chat['id']
    redis = context.bot_data['redis']
    current_quiz = redis.hgetall(chat_id)
    if not redis.get(f'{chat_id}:total'):
        redis.set(f'{chat_id}:total', '0')

    if current_quiz:
        if update.message.text.lower() == current_quiz['Ответ'].lower():
            update.message.reply_text(
                f'Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»'
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
        'quiz': generate_quiz(files_to_collect=2)
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

    updater.start_polling()
    updater.idle()
