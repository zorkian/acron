## acron

This is a cron replacement system written in Python.

This was written because I'm tired of how difficult cron is to manage in large environments. With thousands of machines each running a dozen cron jobs and a hundred+ individual types of jobs, you end up repeating a lot of functionality in each job. This functionality can best be expressed outside of the standard system cron. 

## usage

First, set up a directory (it can be a directory tree with subdirs, etc) that contains cron files. Then, run acron.py and point it at this location. It will start watching all of the files in the tree and load cron jobs from them.

I actually recommend running acron from cron every minute. Acron will end up being long running and maintain your jobs and it will just make sure only one copy is every running.

## cron definition

Defining a job is pretty straightforward. The simplest job is just:

    every 10m
    run /usr/local/bin/mycommand.sh

This will run the command every 10 minutes exactly like the system cron would. Any output will be mailed to root@localhost, or whoever the default mailto is specified to be on the command line.

However, if that's all you want to do, you probably don't want to be using acron. A more fully featured description of a job could be:

    every 10m
    timeout 1m  # kill if running longer than 60s
    splay  # see splay section
    
    output if-error mark@example.com  # output is emailed here if job errors
    output /var/log/acron/myjob.log  # all output is appended here
    error if-stderr if-nonzero  # conditions for failure
    
    if /usr/local/bin/machine_in_group.sh mygroup
    
    run /usr/local/bin/something.py --with-some-args --and-args
            --and-more-args --and-even-more --you-get-the-idea

For this example, the `something.py` script is run every 10 minutes, logs all output to a file, and if an error is encountered, it mails the output to the email address given (using the local SMTP server).

## splay and timing

By default, a clause like `every 10m` will trigger the job like you expect from normal cron systems: at 0 past the hour, 10 past, 20 past, etc. In a large environment, however, this can be quite unfortunate: thousands of servers all triggering a disk cleanup at the same time can lead to quite a few errors or badly increased latency for your environment.

One way of handling this problem is to have a random jitter for jobs: i.e., for the above 10m job, you actually run the job in 0-20m so that it averages out to 10m between runs. This is fine for some jobs, but there are some edge cases where this is not ideal. Sometimes you do want jobs to run 10m apart almost exactly, it's just that you don't care when the timer starts as long as the interval is correct.

Another problem with random offsets is the restart problem. If you picked an offset of 150 seconds, then your job would be running at start+150, start+600+150, start+1200+150, etc. This would work until you restarted acron, at which point the random 150 would change and now you can't guarantee the interval of your job.

A better way to handle this is with a so-called consistent splay. We calculate it by taking the hostname of the machine (which we assume to be globally unique in the infrastructure) and hashing it down to a value. This means that every time you run acron, it will pick the same offset for the same interval on the same machine. Your job will always run 10m apart, even if you restart acron.

## timeout handling

If you specify a timeout for your job, acron will let it run for that period of time before sending a SIGTERM. We will then give you another timeout interval to exit, but if you don't, we'll send a SIGKILL. Either way we will consider the job to have failed and trigger error handling.

## output handling

Acron lets you specify some tunables for output. The basic is just where to send the output, which is either a filename (to be appended to) or an email address.

    output /var/log/something.log
    output /dev/null
    output mark@example.com

These are all valid ways to handle output. Acron gives you the ability to specify one more flag for output: `if-error`. If specified, this means to only trigger that output line if an error condition is encountered with the job. For example, you could email output only if there are errors:

    output if-error mark@example.com

Now, what is an error? Acron decides a cron has failed if it returns a non-zero exit code. This is standard Unix behavior. Return 0 if you succeed.

If this behavior doesn't work for you, you can specify the error conditions per job like this:

    error if-stderr if-nonzero

The available flags: `if-stderr` means that a job is considered failed if it prints anything to STDERR, and `if-nonzero` will consider nonzero return codes to be failures. If you specify only one flag, the other is assumed to be false.

## pre-commands ("if")

There are sort of two ways to go about specifying that a cron should be run or not: either just have the file present (no if clause) or to specify an if clause.

Acron will, upon encountering an if clause in a job specification, execute that command. If the command returns successfully (a 0 return code), then the job is considered to be "valid" and we insert it into the runnable list. If, however, the if command returns a nonzero value, then we do not run the job.

## bugs

Many. Very early project.
