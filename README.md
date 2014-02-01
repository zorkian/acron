# acron

This is a cron replacement system.

# usage

First, set up a directory (it can be a directory tree with subdirs, etc) that contains cron files.
Then, run acron.py and point it at this location. It will start watching all of the files in the
tree and load cron jobs from them.

I actually recommend running acron from cron every minute. Acron will end up being long running
and maintain your jobs and it will just make sure only one copy is every running.

# bugs

Many. Very early project.
