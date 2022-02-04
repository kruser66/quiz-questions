import os
import logging
import redis
import vk_api as vk
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from dotenv import load_dotenv
from random import choice
from quiz_maker import generate_quiz


logger = logging.getLogger('quiz-logger')

keyboard = VkKeyboard()

keyboard.add_button('Новый вопрос', color=VkKeyboardColor.PRIMARY)
keyboard.add_button('Сдаться', color=VkKeyboardColor.NEGATIVE)

keyboard.add_line()
keyboard.add_button('Мой счет', color=VkKeyboardColor.SECONDARY)


def start(event, vk_api, redis):
    vk_api.messages.send(
        user_id=event.user_id,
        message='''Привет! Я бот-викторина!
        Нажми "Новый вопрос", чтобы начать.
        Напишите "Стоп", чтобы закончить.''',
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard()
    )
    redis.set(f'{event.user_id}:start', '1')


def cancel(event, vk_api, redis):
    user = vk_api.users.get(user_ids=event.user_id)[0]["first_name"]
    vk_api.messages.send(
        user_id=event.user_id,
        message=f'До скорых встреч {user}!',
        random_id=get_random_id(),
        keyboard=keyboard.get_empty_keyboard()
    )
    redis.set(f'{event.user_id}:start', '0')


def new_question_request(event, vk_api, collection_quiz, redis):
    chat_id = event.user_id

    quiz = choice(collection_quiz)
    vk_api.messages.send(
        user_id=chat_id,
        message=quiz['Вопрос'],
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard()
    )
    for key in redis.hkeys(chat_id):
        redis.hdel(chat_id, key)
    redis.hset(chat_id, mapping=quiz)


def surrender(event, vk_api, redis):
    chat_id = event.user_id
    current_quiz = redis.hgetall(chat_id)

    vk_api.messages.send(
        user_id=chat_id,
        message=f'Ответ: {current_quiz["Ответ"]}',
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard()
    )
    if 'Комментарий' in current_quiz:
        vk_api.messages.send(
            user_id=chat_id,
            message=f'Комментарий: {current_quiz["Комментарий"]}',
            random_id=get_random_id(),
            keyboard=keyboard.get_keyboard()
        )


def solution_attempt(event, vk_api, redis):
    chat_id = event.user_id
    if redis.get(f'{chat_id}:start') != '1':
        return
    current_quiz = redis.hgetall(chat_id)
    if not redis.get(f'{chat_id}:total'):
        redis.set(f'{chat_id}:total', '0')

    if current_quiz:
        if event.text.lower() == current_quiz['Ответ'].lower():
            vk_api.messages.send(
                user_id=chat_id,
                message='''Правильно! Поздравляю!
                Чтобы продолжить нажми «Новый вопрос»''',
                random_id=get_random_id(),
                keyboard=keyboard.get_keyboard()
            )
            redis.incr(f'{chat_id}:total')

        else:
            vk_api.messages.send(
                user_id=chat_id,
                message='Неправильно… Попробуешь ещё раз?',
                random_id=get_random_id(),
                keyboard=keyboard.get_keyboard()
            )


def total_request(event, vk_api, redis):
    chat_id = event.user_id

    total = redis.get(f'{chat_id}:total')
    vk_api.messages.send(
        user_id=chat_id,
        message=f'Количество Ваших верных ответов: {total if total else 0}',
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard()
    )


if __name__ == "__main__":

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    load_dotenv()

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

    vk_token = os.environ['VK_GROUP_TOKEN']

    vk_session = vk.VkApi(token=vk_token)
    vk_api = vk_session.get_api()

    longpoll = VkLongPoll(vk_session)

    quiz = generate_quiz(files_to_collect=2)

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            print(event)
            print(dir(event))
            if event.text == 'Новый вопрос':
                new_question_request(event, vk_api, quiz, db_redis)
            elif event.text == 'Сдаться':
                surrender(event, vk_api, db_redis)
            elif event.text == 'Мой счет':
                total_request(event, vk_api, db_redis)
            elif event.text == 'Начать':
                start(event, vk_api, db_redis)
            elif event.text == 'Стоп':
                total_request(event, vk_api, db_redis)
                cancel(event, vk_api, db_redis)
            else:
                solution_attempt(event, vk_api, db_redis)
