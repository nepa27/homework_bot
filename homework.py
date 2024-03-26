import sys
from http import HTTPStatus
import os
import logging
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import (BadStatusException, BadTokensException,
                        EmptyResponseFromAPI)

load_dotenv()

log_format = ('%(asctime)s - [%(levelname)s] -  %(name)s - '
              '(%(filename)s).%(funcName)s(%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setFormatter(
    logging.Formatter(log_format)
)

file_handler = logging.FileHandler(f'{__file__}.log')
file_handler.setFormatter(logging.Formatter(log_format))

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = (
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
    )
    check_value = True
    for names, token in tokens:
        if token is None:
            check_value = False
            logger.critical(
                f'Отсутствует переменная окружения {names}'
            )
    if not check_value:
        raise BadTokensException(
            'Отсутствует переменная окружения'
        )
    logger.debug('Все переменные окружения доступны.')


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logger.error(
            f'Ошибка при отправке сообщения в Telegram: {error}'
        )
        return False
    logger.debug(f'Сообщение: "{message}" отправлено в Telegram.')
    return True


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту."""
    requests_options = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': f'{timestamp}'}
    }
    message = (f'{requests_options["url"]}'
               f'с заголовком {requests_options["headers"]}'
               f'и параметрами {requests_options["params"]}')
    logger.debug(f'Начат запрос к API {message}')
    try:
        response = requests.get(
            requests_options['url'],
            headers=requests_options['headers'],
            params=requests_options['params']
        )
    except requests.RequestException as error:
        logger.error(
            f'Ошибка запроса к API: {error} {message}'
        )
        raise ConnectionError(
            f'Ошибка запроса к API: {error} {message}'
        )
    finally:
        if response.status_code != HTTPStatus.OK:
            raise requests.exceptions.HTTPError(
                f'Запрос к эндпоинту {requests_options["url"]} '
                f'вернул статус-код: {response.status_code},'
                f'причина: {response.reason},'
                f'с текстом {response.text}'
            )
        logger.debug(f'Выполнен удачный запрос к API '
                     f'{requests_options["url"]}')
        return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logger.debug('Начата проверка API на релевантность.')
    key_homeworks = 'homeworks'
    if not isinstance(response, dict):
        error = f'Структура данных {type(response)} не является dict'
        logger.error(error)
        raise TypeError(error)
    if response.get(key_homeworks) is None:
        error = f'Отсутствует ключ {key_homeworks} в ответе API'
        logger.error(error)
        raise EmptyResponseFromAPI(error)
    homeworks = response.get(key_homeworks)
    if not isinstance(homeworks, list):
        error = f'Данные под ключом {key_homeworks} приходят не в виде списка'
        logger.error(error)
        raise TypeError(error)
    logger.debug('Получен релевантный ответ от API.')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        message = (f'Полученный статус {homework_status} отсутствует '
                   f'в словаре вердиктов')
        logger.error(message)
        raise BadStatusException(message)
    try:
        homework_name = homework['homework_name']
    except KeyError as error:
        message = f'Ошибка в структуре статуса домашней работы: {error}'
        logger.error(message)
        raise KeyError(message)
    return (f'Изменился статус проверки работы "{homework_name}".'
            f' {HOMEWORK_VERDICTS[homework_status]}')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    previous_message = ''
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                message = ('Ошибка! В полученном от API ответе нет '
                           'информации о домашней работе.')
                logger.error(message)
                if message != previous_message:
                    if send_message(bot, message):
                        previous_message = message
                continue
            logger.debug('Получена информация о домашней работе.')
            message = parse_status(homeworks[0])
            timestamp = 0
            if message != previous_message:
                send_message(bot, message)
                previous_message = message
                timestamp = response.get('time')
            else:
                logger.debug('Статус домашней работы не изменился.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'{message}')
            if message != previous_message:
                if send_message(bot, message):
                    previous_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
