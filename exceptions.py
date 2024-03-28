class EmptyResponseFromAPI(Exception):
    """Вызывается, когда API не возвращает homeworks."""
    pass


class BadTokensException(Exception):
    """Вызывается, когда отсутствует один из токенов."""
    pass
