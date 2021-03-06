import datetime
import sys, logging
from pymongo import MongoClient


def error_logging_decorator(func):
    def func_wrapper(*args, **kwargs):
        self = args[0]
        qid = func.__name__
        try:
            return func(*args, **kwargs)
        except Exception as e:
            msg = qid + ' => ' + str(e)
            if self and hasattr(self, 'logger'):
                self.logger.error(msg)
            else:
                logging.getLogger(qid).error(msg)
            raise e

    return func_wrapper


class MongoHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET, host='localhost', port=27017, db='python_import', collection='error',
                 formatter=None):
        logging.Handler.__init__(self, level)
        self.default_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.formatter = formatter or logging.Formatter(self.default_formatter_str)
        self.client = MongoClient(host=host, port=port)
        self.collection = self.client.get_database(db).get_collection(collection)

    def emit(self, record: logging.LogRecord):
        try:
            self.format(record)
            self.format_time(record)
            self.collection.insert_one(self.transform(record))
        except:
            import traceback
            ei = sys.exc_info()
            traceback.print_exception(ei[0], ei[1], ei[2], None, sys.stderr)
            del ei

    def transform(self, record: logging.LogRecord):
        return {
            'name': record.name,
            'time': record.db_time_dt,
            'level': record.levelname,
            'message': record.getMessage()
        }

    def format_time(self, record: logging.LogRecord):
        record.db_time_dt = datetime.datetime.fromtimestamp(record.created)

    def close(self):
        self.client.close()
        logging.Handler.close(self)
