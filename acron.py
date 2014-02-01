#!/usr/bin/env python
'''

    acron.py -- a cron replacement tool

    This is designed to be a replacement for the system cron. You can run acron and it will behave
    almost exactly like you expect the system cron to work, except there are some more advanced
    behaviors that can be expressed.

    Rationale: many cron jobs need to do similar kinds of tasks, and instead of implementing those
    functionalities in each and every cron, they can be implemented in the cron runner level.

'''

import argparse
import sys
import logging
import os
import re
import socket
import time
import hashlib
import subprocess


class Job(object):
    '''
    A Job represents a single job that we might be running. It maintains information about the
    job parameters and whether or not the job is running, plus handles locking, running, collating
    output, etc.
    '''
    def __init__(self, filename):
        '''
        Initializes a job from a given file. We also start watching the file and, if it happens to
        go away, then we disable the job before the next scheduled execution.
        '''
        self.filename = filename
        self.mtime = os.stat(filename).st_mtime
        self.command = ''
        self.errors = False
        self.next_run_ts = None
        self.running = False
        self.if_command = None

        in_command = False
        for line in open(filename).readlines():
            c_line = ' '.join(line.split('#')[0].strip().split())
            if in_command and line.startswith(' '):
                self.command += ' ' + c_line
                continue
            else:
                in_command = False

            if not c_line:
                continue
            if ' ' in c_line:
                cmd, args = c_line.split(' ', 1)
            else:
                cmd, args = c_line, ''

            if cmd == 'run':
                self.command = args
                in_command = True

            if cmd == 'if':
                self.if_command = args

            elif cmd == 'every':
                self.every = self._parse_time(cmd, args)

            elif cmd == 'timeout':
                self.timeout = self._parse_time(cmd, args)

            elif cmd == 'send-stdout':
                if args not in ('if-stderr', 'always', 'never'):
                    logging.error('%s: send-stdout not valid', filename)
                    self.errors = True
                self.send_stdout = args

            elif cmd == 'stderr':
                if not (args.startswith('/') or '@' in args or args == 'stdout'):
                    logging.error('%s: stderr not filename, email, or "stdout"', filename)
                    self.errors = True
                self.stderr = args

            elif cmd == 'stdout':
                if not (args.startswith('/') or '@' in args or args == 'stderr'):
                    logging.error('%s: stdout not filename, email, or "stderr"', filename)
                    self.errors = True
                self.stdout = args

            elif cmd == 'splay':
                if args not in ('on', 'off'):
                    logging.error('%s: splay must be "on" or "off"', filename)
                    self.errors = True
                self.splay = True if args == 'on' else False

    def _parse_time(self, cmd, arg):
        '''
        Internal function: parses a time value input by a user.
        '''
        converts = {'hour': '1h', 'minute': '1m', 'day': '1d'}
        if arg in converts:
            arg = converts[arg]
        if not re.match('^\d+[dhms]$', arg):
            logging.error('%s: %s value does not match formatting rules', self.filename, cmd)
            self.errors = True
            val = 1
        else:
            val = int(arg[0:-1]) * {'d': 86400, 'h': 3600, 'm': 60, 's': 1}[arg[-1]]
        if not val or val < 1:
            val = 3600  # This is to prevent failures if we can't parse the time.
        return val

    def next_run(self):
        '''
        next_run returns the number of seconds this job is waiting until it's next eligible to
        run. If this has never been called, we'll calculate the time, else we'll just wait for
        the time we've already calculated (helping prevent skips).
        '''
        if self.errors:
            return None
        if self.next_run_ts is not None:
            return self.next_run_ts
        now = int(time.time())
        # Next run times are always calculated from the last non-splayed offset. I.e., if we
        # run every minute, we go back to the last minute boundary and project forward from
        # there. If we've missed the splay point, we add it twice to get the next point.
        start_ts = now - (now % self.every)
        if not self.splay:
            self.next_run_ts = start_ts + self.every
        else:
            self.next_run_ts = start_ts + int(hashlib.md5(socket.gethostname()).hexdigest(), 16) % self.every
        if self.next_run_ts < now:
            self.next_run_ts += self.every
        return self.next_run_ts

    def run(self):
        '''
        run executes the cron job. It gets run in a subprocess.
        '''
        logging.info('Running %s', self.filename)
        self.next_run_ts = None
        #self.running = True

    def try_reaping(self):
        '''
        try_reaping will check the status of a running job and, if necessary, reap it, kill it, or
        do some other maintenance.
        '''
        pass


def main(crondir):
    '''
    main function of acron, handles the global state management, updating our crons, and then
    kicking off jobs.
    '''
    jobs = {}
    while True:
        # Job definition update loop.
        now = int(time.time())
        if now % 10 == 0:
            logging.info('Acron loop: %d jobs watched', len(jobs))
        for root, dirs, files in os.walk(args.cron_dir):
            for fn in files:
                filename = os.path.join(root, fn)
                if filename in jobs:
                    job = jobs[filename]
                    if job.mtime < os.stat(filename).st_mtime:
                        if job.running:
                            logging.info('%s needs update, but still running', filename)
                            continue  # next file.
                        else:
                            logging.info('%s changed, reloading...', filename)
                            del jobs[filename]
                            job = Job(filename)
                    else:
                        continue
                else:
                    job = Job(filename)
                if job.if_command:
                    try:
                        subprocess.check_output(['/bin/bash', '-c', job.if_command],
                                                stderr=subprocess.STDOUT)
                    except subprocess.CalledProcessError:
                        logging.debug('%s: "if" returned error, skipping job', filename)
                        continue
                jobs[filename] = job
                print jobs[filename].next_run(), jobs[filename].command

        # Job execution loop.
        for job in jobs.itervalues():
            if job.errors:
                logging.debug('%s: has errors, skipping', job.filename)
                continue
            if job.running:
                logging.debug('%s: is running', job.filename)
                job.try_reaping()
                continue
            timeleft = job.next_run() - now
            logging.debug('%s: timeleft = %d', job.filename, timeleft)
            if timeleft > 0:
                continue
            # Actually run the job now.
            job.run()

        time.sleep(1)
    return 0


def usage():
    print '''acron -- a cron replacement

Blah blah, a usage file should be here.
'''
    sys.exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='acron manager')
    parser.add_argument('--cron-dir', help="Directory of files to watch for crons")
    parser.add_argument('-v', dest='verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s %(levelname)s] %(message)s')
    log = logging.getLogger()
    if args.verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    if not args.cron_dir:
        usage()
    if not os.path.isdir(args.cron_dir):
        logging.error('%s is not a directory', args.cron_dir)
        sys.exit(1)

    # TODO: add some locking to prevent multiple acrons from running.
    logging.info('Acron beginning run')
    sys.exit(main(args.cron_dir))
