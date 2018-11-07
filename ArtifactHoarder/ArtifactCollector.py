from datetime import datetime
from subprocess import Popen, PIPE, CalledProcessError
import logging
import shlex
import os
import sys

SUPERUSER_ID = 0
FILE_NOT_FOUND_ERROR_CODE = 1
SUPERUSER_ERROR_CODE = 2
LOG = '/var/log/artifactcollector/{{{}}}.log'
OUTPUT_DIRECTORY = 'output/'
ROOT_DIR = '/'
PRINT_COMMAND = 'find %s -type f -exec cat {} +'
LIST_COMMAND = 'find %s -type f -exec ls {} +'
COMMANDS = {'kernel_name_version'   : ['uname -rs'],
            'kernel modules'        : ['lsmod'],
            'network interfaces'    : ['ifconfig -a'],
            'networking information': [PRINT_COMMAND % '/etc/hosts',
                                       PRINT_COMMAND % '/etc/networks',
                                       PRINT_COMMAND % '/etc/protocols',
                                       PRINT_COMMAND % '/etc/ethers',
                                       PRINT_COMMAND % '/etc/netgroup',
                                       PRINT_COMMAND % '/etc/dhclients'],
            'hostname'              : ['hostname',
                                       PRINT_COMMAND % '/etc/hostname'],
            'login history'         : ['last -Faixw',
                                       PRINT_COMMAND % '/etc/logs/auth.log',
                                       PRINT_COMMAND % '/etc/logs/secure',
                                       PRINT_COMMAND % '/etc/logs/audit.log'],
            'unix distribution'     : [PRINT_COMMAND % '/etc/*release'],
            'socket connections'    : ['ss -p',
                                       'ss -naop'],
            'processes'             : ['ps -eww'],
            'password files'        : [PRINT_COMMAND % '/etc/shadow',
                                       PRINT_COMMAND % '/etc/passwd'],
            'scheduled jobs'        : [PRINT_COMMAND % '/etc/cron*',
                                       PRINT_COMMAND % '/var/spool/cron/*'],
            'x window config files' : [PRINT_COMMAND % '/etc/X11/*'],
            'yum repositories'      : [PRINT_COMMAND % '/etc/yum.repos.d/*'],
            'cached yum data files' : [LIST_COMMAND % '/var/cache/yum'],
            'installed yum packages': ['yum list installed'],
            'startup scripts'       : [PRINT_COMMAND % '/etc/rc.d/*',
                                       PRINT_COMMAND % '/etc/init*'],
            'open files'            : ['lsof -R'],
            'ssh configuration'     : [PRINT_COMMAND % '$HOME/.ssh'],
            'user commands'         : [LIST_COMMAND % '/usr/bin',
                                       LIST_COMMAND % '/usr/local/bin'],
            'process tree'          : ['pstree -alp']}


class ArtifactCollector(object):
    def __init__(self):
        self.logger = logging.getLogger()
        self.start_logging()
        self.check_root_access()
        self.check_directories()
        self.call_commands()

    #   start_logging()
    #   Begin logging execution
    def start_logging(self):
        self.logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s %(levelname)-8s- - - %(message)s')

        file_handler = logging.FileHandler(LOG.replace('{{{}}}', r'{date:%Y-%m-%d_%H:%M:%S}'.format(date=datetime.now())))
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        clo_handler = logging.StreamHandler()
        clo_handler.setLevel(logging.DEBUG)
        clo_handler.setFormatter(formatter)
        self.logger.addHandler(clo_handler)


        self.logger.info('Started execution')

    # check_root_access()
    # Checks for the runtime's effective user ID permissions, exits if not enough access to collect artifacts
    def check_root_access(self):
        self.logger.info('Checking effective user permissions')
        if os.geteuid() != SUPERUSER_ID:
            self.logger.info("Runtime does not have superuser privileges. Re-run program with sudo. Exiting...")
            sys.exit(SUPERUSER_ERROR_CODE)
        else:
            self.logger.info('Confirmed superuser privileges, running...')
            return

    # check_directories()
    # Sets up directory structure for file IO, ensures correct hierarchy for successful writing
    def check_directories(self):
        self.logger.info('Checking directory structure...')
        section_directories = map(lambda x: x.replace(' ', '_'), COMMANDS)

        for section in section_directories:
            if not os.path.exists(OUTPUT_DIRECTORY + section):
                os.mkdir(OUTPUT_DIRECTORY + section)
                self.logger.info('Directory %s does not exist, creating...' % section)
            else:
                self.logger.info('Directory %s exists' % section)

    # call_commands()
    # Function to iterate through the command dictionary and executing each command. It saves runtime information to the
    # log file and keeps track of unsuccessful commands.
    def call_commands(self):
        for section in COMMANDS:
            for command in COMMANDS[section]:
                self.logger.info(section.upper() + ' | command: ' + command)
                try:
                    process = Popen(shlex.split(command), stdout=PIPE)
                    output = process.stdout.read().decode('ascii')
                    self.save_output(section, command, output)
                except OSError as e:
                    self.logger.warning('Unknown command or file -  ' + str(e))
                except CalledProcessError:
                    self.logger.warning('Could not find command!')
                except UnicodeDecodeError:
                    self.logger.warning('Error decoding unicode output.')
                except AttributeError:
                    self.logger.warning('Attribute error')
                else:
                    if process == FILE_NOT_FOUND_ERROR_CODE:
                        self.logger.warning('File does not exist, unable to run command: ' + command)

    def save_output(self, section, command, output):
        fname = os.path.join(OUTPUT_DIRECTORY + section.replace(' ', '_'), command.replace(' ', '_').replace('/', '_')
                             + '.txt')
        self.logger.info('Saving output to %s' % fname)
        file = open(fname, 'w')
        file.write(output)
        file.close()
        self.logger.info('Saved ./%s/%s successfully' % (section, command))