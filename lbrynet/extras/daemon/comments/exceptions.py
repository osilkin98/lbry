

class MetadataServerException(Exception):
    """ Base Exception to handle errors returned from the server """

    def __str__(self) -> str:
        return str(self.response)

    def __init__(self, result, *args) -> None:
        self.request_id = result['id']
        self.code = result['error']['code']
        self.message = result['error']['message'] if 'message' in result['error'] else None
        self.response = result
        super().__init__(*args)


class GenericServerError(MetadataServerException):
    """ This is for any standard JSON-RPC errors that aren't documented by the Comment API """


class InternalMetadataServerError(MetadataServerException):
    """ This is for status code -32603 """


class InvalidParamsError(MetadataServerException):
    """ This is for status code -32602 """


class InvalidClaimUriError(MetadataServerException):
    """ This is for status code 1 """


class UnknownMetadataServerError(MetadataServerException):
    """ This is for everything with the status code -1 """


MetadataExceptions = {
    -32603: InternalMetadataServerError,
    -32602: InvalidParamsError,
    -1: UnknownMetadataServerError,
    1: InvalidClaimUriError
}
