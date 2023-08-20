import sys
import logging
import os

class Logger():
    def __init__(self, log_path=''):
        __log_formatter = logging.Formatter('%(levelname)s %(asctime)s :: %(message)s', 
                                        datefmt='%d/%m/%Y %H:%M:%S')
        #Setup Stream Handler (i.e. console)
        __stream_handler = logging.StreamHandler(sys.stdout)
        __stream_handler.setFormatter(__log_formatter)
        __stream_handler.setLevel(logging.INFO)

        #Get our logger
        self.__logger = logging.getLogger('root')
        self.__logger.setLevel(logging.INFO)

        if log_path and not self.handler_exists(log_path):
            #Setup File handler
            __file_handler = logging.FileHandler(log_path)
            __file_handler.setFormatter(__log_formatter)
            __file_handler.setLevel(logging.INFO)
            self.__logger.addHandler(__file_handler)

        if not self.stream_handler_exists():
            self.__logger.addHandler(__stream_handler)


    def handler_exists(self, log_path):
        for handler in self.__logger.handlers:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath(log_path):
                return True
        return False

    def stream_handler_exists(self):
        for handler in self.__logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                return True
        return False
    
    def log(self, message):
        self.__logger.info(message)
		
    def error(self, message):
        self.__logger.error(message)

    def clear_old_log(self, log_filename: str):
        if os.path.exists(log_filename):
            os.remove(log_filename)
            self.__logger.info("Old log file {} cleared".format(self.log_filename))