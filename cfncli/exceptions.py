import json
from http import HTTPStatus



class ApplicationException(Exception):
    """Base exception class for application."""

    def __init__(self, message, status_code=500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DesiredStateNotReached(Exception):
    def __init__(self, message, status_code=500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class HttpException(Exception):
    def __init__(self, status_code: HTTPStatus, message: str):
        self.status_code = status_code.value
        self.message = message


class BadRequestException(HttpException):
    def __init__(self, message):
        super().__init__(HTTPStatus.BAD_REQUEST, message)


class NotFoundException(HttpException):
    def __init__(self, message):
        super().__init__(HTTPStatus.NOT_FOUND, message)


class InternalServerErrorException(HttpException):
    def __init__(self, message):
        super().__init__(HTTPStatus.INTERNAL_SERVER_ERROR, message)


class UnprocessableEntityException(HttpException):
    def __init__(self, message):
        super().__init__(HTTPStatus.UNPROCESSABLE_ENTITY, message)


class TooManyRequestsException(HttpException):
    def __init__(self, message):
        super().__init__(HTTPStatus.TOO_MANY_REQUESTS, message)
