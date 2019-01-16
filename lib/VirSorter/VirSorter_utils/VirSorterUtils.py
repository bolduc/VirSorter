import os
import subprocess
import time

from installed_clients.DataFileUtilClient import DataFileUtil as dfu


def log(message, prefix_newline=False):
    """
    Logging function, provides a hook to suppress or redirect log messages.
    """
    print(('\n' if prefix_newline else '') + '{0:.2f}'.format(time.time()) + ': ' + str(message))


class VirSorterUtils:

    def __init__(self, config):
        self.scratch = os.path.abspath(config['scratch'])

    def VirSorter_help(self):
        command = 'wrapper_phage_contigs_sorter_iPlant.pl --help'
        self._run_command(command)

    def run_VirSorter(self, params):

        mapping = {
            'genomes': '-f',
            'database': '--db',
            'add_genomes': '--cp',  # Custom phage sequences
        }

        command = 'wrapper_phage_contigs_sorter_iPlant.pl'

        for param, cmd in mapping.items():
            command += ' {} {}'.format(cmd, params[param])

        bool_args = ['virome', 'diamond', 'keep_db', 'no_c']  # keep_db = keep-db

        self._run_command(command)

        report = self._generate_report(params)

        return report

    def _run_command(self, command):
        """

        :param command:
        :return:
        """

        log('Start executing command:\n{}'.format(command))
        pipe = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        output = pipe.communicate()[0]
        exitCode = pipe.returncode

        if (exitCode == 0):
            log('Executed command:\n{}\n'.format(command) +
                'Exit Code: {}\nOutput:\n{}'.format(exitCode, output))
        else:
            error_msg = 'Error running command:\n{}\n'.format(command)
            error_msg += 'Exit Code: {}Output:\n{}'.format(exitCode, output)

    def _generate_report(self, params):
        """

        :param params:
        :return:
        """

        # Get URL
        self.dfu = dfu(params['SDK_CALLBACK_URL'])

    def _mkdir_p(self, path):
        """
        :param path:
        :return:
        """

        if not path:
            return
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise
