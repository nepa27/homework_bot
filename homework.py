from http import HTTPStatus
import os
import logging
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import RequestAPIException

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)

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
    if None in (
            PRACTICUM_TOKEN,
            TELEGRAM_TOKEN,
            TELEGRAM_CHAT_ID
    ):
        logging.critical(
            'Отсутствует одна из переменных окружения'
        )
        exit()
    logging.debug('Все переменные окружения доступны.')


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение: {message} отправлено в Telegram.')
    except telegram.error.BadRequest as error:
        logging.error(
            f'Ошибка при отправке сообщения в Telegram: {error}'
        )
        raise telegram.error.BadRequest(
            f'Ошибка при отправке сообщения в Telegram: {error}'
        )


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': f'{timestamp}'}
        )
        if response.status_code != HTTPStatus.OK:
            logging.error(
                f'Запрос к эндпоинту {ENDPOINT} вернул статус-код: '
                f'{response.status_code}'
            )
            raise requests.exceptions.HTTPError(
                f'Запрос к эндпоинту {ENDPOINT}  вернул статус-код: '
                f'{response.status_code}'
            )
        logging.debug(f'Выполнен удачный запрос к эндпоинту {ENDPOINT}')
        return response.json()
    except requests.RequestException as error:
        logging.error(
            f'Ошибка запроса к API: {error}'
        )
        raise RequestAPIException(
            f'Ошибка запроса к API: {error}'
        )


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    key_homeworks = 'homeworks'
    if type(response) != dict:
        error = f'Структура данных {type(response) }не является dict'
        logging.error(error)
        raise TypeError(error)
    if response.get(key_homeworks) is None:
        error = f'Отсутствует ключ {key_homeworks} в ответе API'
        logging.error(error)
        raise KeyError(error)
    if type(response.get(key_homeworks)) != list:
        error = f'Данные под ключом {key_homeworks} приходят не в виде списка'
        logging.error(error)
        raise TypeError(error)
    logging.debug('Получен релевантный ответ от API.')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    try:
        homework_name = homework['homework_name']
        verdict = HOMEWORK_VERDICTS[homework.get('status')]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError as error:
        message = f'Ошибка в структуре статуса домашней работы: {error}'
        logging.error(message)
        raise KeyError(message)


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    previous_message = None
    while True:
        try:
            timestamp = int(time.time())
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            if len(homeworks) != 0:
                logging.debug('Получена информация о домашней работе.')
                message = parse_status(homeworks[0])
            else:
                message = ('Ошибка! В полученном от API ответе нет '
                           'информации о домашней работе.')
                logging.error(message)
            if message != previous_message:
                send_message(bot, message)
                previous_message = message
            else:
                logging.debug('Статус домашней работы не изменился.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(f'{message}')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
