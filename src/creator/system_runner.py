import subprocess
import time
from .logger import Logger

class Runner:
    def __init__(self, external_logger: Logger = ''):
        if external_logger == '':
            self.__logger = Logger()
        else:
            self.__logger = external_logger

    def run(self, bashCommand: str, exclude_errors: list = [], silent = False):
        """ Run commands in shell
        Get 
            command: str, 
            logger: Logger, by deafult import from logger
            exclude_errors: list, exclude array list of errors to output in logger
        Return error status from shell Int
        """
        if not silent: self.__logger.log("Run command: " + bashCommand)
        process = subprocess.Popen(bashCommand, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        while True:
            line = process.stdout.readline()
            err = process.stderr.readline()
            if not line and not err:
                break
            elif line:
                if not silent: self.__logger.log(">>> {}".format(line.rstrip()))
            elif err:
                error_message: str = err.rstrip().decode('utf-8')
                show_err = True
                for word in exclude_errors:
                    if error_message.find(word) >= 0:
                        show_err = False
                if show_err:
                    self.__logger.error(">>> {}".format(error_message))
        # Wait until process terminates (without using p.wait())
        while process.poll() is None:
        # Process hasn't exited yet, let's wait some
            time.sleep(0.5)

        # Get return code from process
        return_code = process.returncode

        if not silent: self.__logger.log("Return code {}".format(return_code))
        return return_code