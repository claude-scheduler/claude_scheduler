#!/usr/bin/env python3

"""
Task Scheduler - Background thread for scheduling and executing tasks.

Extracted and modernized from lightControl's TaskSchedulerTask and
TaskScheduler classes.
"""

import time
import threading

# Global state
task_scheduler_should_terminate = False
task_schedule = []
schedule_lock = threading.Lock()

# Convenience lambdas
current_hour = lambda t: t.tm_hour
current_minute = lambda t: t.tm_min


class TaskSchedulerTask:
    """
    Base task class supporting both time-based and periodic scheduling.
    """

    def __init__(self, schedule_time="12:00PM"):
        self.was_activated = False
        self.time = time.strptime(schedule_time, "%I:%M%p")
        self.periodic = False
        self.period = 60  # seconds

    def __repr__(self):
        if self.is_periodic():
            return f"Task every {self.period} seconds"
        else:
            return f"Task at {time.strftime('%I:%M%p', self.time)}"

    def get_time(self):
        """Return the scheduled time."""
        return self.time

    def get_hour(self):
        """Return the scheduled hour."""
        return current_hour(self.time)

    def get_minute(self):
        """Return the scheduled minute."""
        return current_minute(self.time)

    def should_activate(self):
        """
        Check if this task should activate now.
        Returns True if the task should execute.
        """
        if not self.is_periodic():
            # Time-based scheduling
            current_time = time.localtime()

            if current_hour(current_time) == self.get_hour():
                if current_minute(current_time) == self.get_minute():
                    if not self.was_activated:
                        self.was_activated = True
                        return True
                    else:
                        return False

            # Reset activation flag when not in the scheduled minute
            self.was_activated = False
            return False

        else:
            # Periodic scheduling
            if self.period > 1:
                if not (int(time.time()) % self.period):
                    if not self.was_activated:
                        self.was_activated = True
                        return True
                    else:
                        return False
                else:
                    self.was_activated = False
                    return False
            else:
                raise Exception("invalid period")

    def is_periodic(self):
        """Return True if this is a periodic task."""
        return self.periodic

    def set_periodic(self, periodic):
        """Set whether this task is periodic."""
        self.periodic = bool(periodic)
        return self.periodic

    def set_period(self, period):
        """Set the period in seconds."""
        self.period = int(period)
        return self.period

    def execute(self):
        """
        Execute the task. Override in subclasses.
        """
        pass


class TaskScheduler(threading.Thread):
    """
    Background thread that polls tasks and executes them when due.
    """

    def __init__(self):
        super().__init__(name="TaskScheduler", daemon=True)

    def run(self):
        """Main scheduler loop."""
        global task_scheduler_should_terminate

        while True:
            if task_scheduler_should_terminate:
                print(f"{self.name}: exiting...")
                return 0

            try:
                with schedule_lock:
                    for task in task_schedule:
                        if task.should_activate():
                            local_time = time.strftime("%I:%M%p", time.localtime())
                            print(f"\n[{local_time}] Activating: {task}")
                            task.execute()

            except Exception as e:
                print(f"Error in scheduler: {e}")

            time.sleep(1)


def get_schedule():
    """Return the current task schedule (thread-safe copy)."""
    with schedule_lock:
        return list(task_schedule)


def add_task(task):
    """Add a task to the schedule."""
    with schedule_lock:
        task_schedule.append(task)


def remove_task(index):
    """Remove a task by index."""
    with schedule_lock:
        if 0 <= index < len(task_schedule):
            del task_schedule[index]
            return True
        return False


def clear_schedule():
    """Clear all tasks from the schedule."""
    global task_schedule
    with schedule_lock:
        task_schedule = []


def set_schedule(tasks):
    """Set the task schedule (used when loading from pickle)."""
    global task_schedule
    with schedule_lock:
        task_schedule = tasks


def stop_scheduler():
    """Signal the scheduler to stop."""
    global task_scheduler_should_terminate
    task_scheduler_should_terminate = True
