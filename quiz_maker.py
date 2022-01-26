import os
import logging
import re
from random import choice

logger = logging.getLogger("quiz_logger")


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


def generate_quiz(files_to_collect=5):
    starts = [
        'Ответ', 'Комментарий'
    ]
    quiz = []
    for _ in range(files_to_collect):
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

    quiz = generate_quiz(2)
