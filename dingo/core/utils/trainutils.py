import time
from os.path import join, isfile
import csv


class AvgTracker():
    def __init__(self):
        self.x = 0
        self.N = 0

    def update(self, x, n):
        self.x += x
        self.N += n

    def get_avg(self):
        if self.N == 0:
            return float('nan')
        return self.x/self.N


class LossInfo():
    def __init__(self, epoch, len_dataset, batch_size, mode='Train',
                 print_freq=1):
        self.epoch = epoch
        self.len_dataset = len_dataset
        self.batch_size = batch_size
        self.mode = mode
        self.print_freq = print_freq
        self.start_time = time.time()
        self.time_last = time.time()
        self.avg_tracker = AvgTracker()

    def update(self, x, n):
        self.avg_tracker.update(x, n)
        t = time.time()
        self.dt = t - self.time_last
        self.time_last = t

    def get_avg(self):
        return self.avg_tracker.get_avg()

    def print_info(self, batch_idx, loss):
        if batch_idx % self.print_freq == 0:
            print('{} Epoch: {} [{}/{} ({:.0f}%)]'.format(
                self.mode,
                self.epoch,
                min(batch_idx * self.batch_size, self.len_dataset),
                self.len_dataset,
                100. * batch_idx * self.batch_size / self.len_dataset
            ), end='\t\t')
            print('Loss (avg): {:.3f} ({:.3f})'.format(
                loss,
                self.get_avg()
            ), end='\t\t')
            print('Time per batch [s] (avg): {:.3f} ({:.3f})'.format(
                self.dt, (time.time() - self.start_time) / (batch_idx + 1)))


class RuntimeLimits:
    """
    Keeps track of the runtime limits (time limit, epoch limit, max. number
    of epochs for model).
    """
    def __init__(self,
                 max_time_per_run: float = None,
                 max_epochs_per_run: int = None,
                 max_epochs_total: int = None,
                 epoch_start: int = None):
        """

        Parameters
        ----------
        max_time_per_run: float = None
            maximum time for run, in seconds
            [soft limit, break only after full epoch]
        max_epochs_per_run: int = None
            maximum number of epochs for run
        max_epochs_total: int = None
            maximum total number of epochs for model
        epoch_start: int = None
            start epoch of run
        """
        self.max_time_per_run = max_time_per_run
        self.max_epochs_per_run = max_epochs_per_run
        self.max_epochs_total = max_epochs_total
        self.epoch_start = epoch_start
        self.time_start = time.time()
        if max_epochs_per_run is not None and epoch_start is None:
                raise ValueError('epoch_start required to check '
                                 'max_epochs_per_run.')

    def runtime_limits_exceeded(self, epoch: int = None):
        """
        Check whether any of the runtime limits are exceeded.

        Parameters
        ----------
        epoch: int = None

        Returns
        -------
        limits_exceeded: bool
            flag whether runtime limits are exceeded and run should be stopped;
            if limits_exceeded = True, this prints a message for the reason
        """
        # check time limit for run
        if self.max_time_per_run is not None:
            if time.time() - self.time_start >= self.max_time_per_run:
                print(f'Stop run: Time limit of {self.max_time_per_run} s '
                      f'exceeded.')
                return True
        # check epoch limit for run
        if self.max_epochs_per_run is not None:
            if epoch is None:
                raise ValueError('epoch required')
            if epoch - self.epoch_start >= self.max_epochs_per_run:
                print(f'Stop run: Epoch limit of {self.max_epochs_per_run} '
                      f'per run reached.')
                return True
        # check total epoch limit
        if self.max_epochs_total is not None:
            if epoch >= self.max_epochs_total:
                print(f'Stop run: Total epoch limit of '
                      f'{self.max_epochs_total} reached.')
                return True
        # return False if none of the limits is exceeded
        return False


def write_history(log_dir, epoch, train_loss, test_loss, learning_rates,
                  aux=[], filename='history.txt'):
    """
    Writes losses and learning rate history to csv file.

    Parameters
    ----------
    log_dir: str
        directory containing the history file
    epoch: int
        epoch
    train_loss: float
        train_loss of epoch
    test_loss: float
        test_loss of epoch
    learning_rates: list
        list of learning rates in epoch
    aux: list = []
        list of auxiliary information to be logged
    filename: str = 'history.txt'
        name of history file
    """
    history_file = join(log_dir, filename)
    if epoch == 1:
        assert not isfile(history_file), \
            f'File {history_file} exists, aborting to not overwrite it.'

    with open(history_file, 'w' if epoch == 1 else 'a') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow([epoch, train_loss, test_loss, *learning_rates, *aux])