"""
TODO: Docstring
"""

from typing import Callable
import torch
import dingo.core.utils as utils
from torch.utils.data import Dataset, DataLoader
import time

import dingo.core.utils.trainutils


class PosteriorModel:
    """
    TODO: Docstring

    Methods
    -------

    initialize_model:
        initialize the NDE (including embedding net) as posterior model
    initialize_training:
        initialize for training, that includes storing the epoch, building
        an optimizer and a learning rate scheduler
    save_model:
        save the model, including all information required to rebuild it,
        except for the builder function
    load_model:
        load and build a model from a file
    train_model:
        train the model
    inference:
        perform inference
    """

    def __init__(self,
                 model_builder: Callable,
                 model_kwargs: dict = None,
                 model_filename: str = None,
                 optimizer_kwargs: dict = None,
                 scheduler_kwargs: dict = None,
                 init_for_training: bool = False,
                 metadata: dict = None,
                 device: torch.device = 'cpu'
                 ):
        """

        Parameters
        ----------

        model_builder: Callable
            builder function for the model,
            self.model = model_builder(**model_kwargs)
        model_kwargs: dict = None
            kwargs for for the model,
            self.model = model_builder(**model_kwargs)
        model_filename: str = None
            path to filename of loaded model
        optimizer_kwargs: dict = None
            kwargs for optimizer
        scheduler_kwargs: dict = None
            kwargs for scheduler
        init_for_training: bool = False
            flag whether initialization for training (e.g., optimizer) required
        metadata: dict = None
            dict with metadata, used to save dataset_settings and train_settings
        """
        self.model_builder = model_builder
        self.model_kwargs = model_kwargs

        self.epoch = 0
        self.optimizer_kwargs = optimizer_kwargs
        self.optimizer = None
        self.scheduler_kwargs = scheduler_kwargs
        self.scheduler = None
        self.metadata = metadata
        self.device = device

        # build model
        if model_filename is not None:
            self.load_model(model_filename,
                            load_training_info=init_for_training)
        else:
            self.initialize_model()
            # initialize for training
            if init_for_training:
                self.initialize_optimizer_and_scheduler()

        # TODO: initialize training and data loader

    def initialize_model(self):
        """
        Initialize a model for the posterior by calling the
        self.model_builder with self.model_kwargs.

        """
        self.model = self.model_builder(**self.model_kwargs)

    def initialize_optimizer_and_scheduler(self):
        """
        Initializes the optimizer and scheduler with self.optimizer_kwargs
        and self.scheduler_kwargs, respectively.
        """
        if self.optimizer_kwargs is not None:
            self.optimizer = utils.get_optimizer_from_kwargs(
                self.model.parameters(), **self.optimizer_kwargs)
        if self.scheduler_kwargs is not None:
            self.scheduler = utils.get_scheduler_from_kwargs(
                self.optimizer, **self.scheduler_kwargs)

    def save_model(self,
                   model_filename: str,
                   save_training_info: bool = True,
                   ):
        """
        Save the posterior model to the disk.

        Parameters
        ----------
        model_filename: str
            filename for saving the model
        save_training_info: bool
            specifies whether information required to proceed with training is
            saved, e.g. optimizer state dict

        """
        model_dict = {
            'model_kwargs': self.model_kwargs,
            'model_state_dict': self.model.state_dict(),
            'epoch': self.epoch,
            # 'training_data_information': None,
        }

        if self.metadata is not None:
            model_dict['metadata'] = self.metadata

        if save_training_info:
            model_dict['optimizer_kwargs'] = self.optimizer_kwargs
            model_dict['scheduler_kwargs'] = self.scheduler_kwargs
            if self.optimizer is not None:
                model_dict['optimizer_state_dict'] = self.optimizer.state_dict()
            if self.scheduler is not None:
                model_dict['scheduler_state_dict'] = self.scheduler.state_dict()
            # TODO

        torch.save(model_dict, model_filename)

    def load_model(self,
                   model_filename: str,
                   load_training_info: bool = True,
                   ):
        """
        Load a posterior model from the disk.

        Parameters
        ----------
        model_filename: str
            path to saved model
        load_training_info: bool #TODO: load information for training
            specifies whether information required to proceed with training is
            loaded, e.g. optimizer state dict
        """

        d = torch.load(model_filename)

        self.model_kwargs = d['model_kwargs']
        self.initialize_model()
        self.model.load_state_dict(d['model_state_dict'])

        self.epoch = d['epoch']

        if 'metadata' in d:
            self.metadata = d['metadata']

        if load_training_info:
            if 'optimizer_kwargs' in d:
                self.optimizer_kwargs = d['optimizer_kwargs']
            if 'scheduler_kwargs' in d:
                self.scheduler_kwargs = d['scheduler_kwargs']
            # initialize optimizer and scheduler
            self.initialize_optimizer_and_scheduler()
            # load optimizer and scheduler state dict
            if 'optimizer_state_dict' in d:
                self.optimizer.load_state_dict(d['optimizer_state_dict'])
            if 'scheduler_state_dict' in d:
                self.scheduler.load_state_dict(d['scheduler_state_dict'])

    def train(self,
              train_loader: torch.utils.data.DataLoader,
              test_loader: torch.utils.data.DataLoader,
              log_dir: str,
              runtime_limits_kwargs: dict = None,
              checkpoint_epochs: int = None,
              ):
        """

        :param train_loader:
        :param test_loader:
        :param log_dir:
        :param runtime_limits_kwargs:
        :return:
        """
        runtime_limits = dingo.core.utils.trainutils.RuntimeLimits(**runtime_limits_kwargs,
                                                                   epoch_start=self.epoch)

        while not runtime_limits.runtime_limits_exceeded(self.epoch):
            self.epoch += 1

            # Training
            lr = utils.get_lr(self.optimizer)
            print(f'\nStart training epoch {self.epoch} with lr {lr}')
            time_start = time.time()
            train_loss = train_epoch(self, train_loader)
            print('Done. This took {:2.0f}:{:2.0f} min.'.format(
                  *divmod(time.time() - time_start, 60)))

            # Testing
            print(f'Start testing epoch {self.epoch}')
            time_start = time.time()
            # test_loss = test_epoch(self, test_loader)
            test_loss = self.epoch * 0.5
            print('Done. This took {:2.0f}:{:2.0f} min.'.format(
                *divmod(time.time() - time_start, 60)))

            utils.write_history(log_dir, self.epoch, train_loss, test_loss, lr)
            utils.save_model(self, log_dir, checkpoint_epochs=checkpoint_epochs)

            # scheduler step for learning rate
            utils.perform_scheduler_step(self.scheduler, test_loss)

            print(f'Finished training epoch {self.epoch}.\n')





def train_epoch(pm, dataloader):
    pm.model.train()
    loss_info = dingo.core.utils.trainutils.LossInfo(pm.epoch, len(dataloader.dataset),
                                                     dataloader.batch_size, mode='Train',
                                                     print_freq=2)

    for batch_idx, data in enumerate(dataloader):
        pm.optimizer.zero_grad()
        # data to device
        data = [d.float().to(pm.device, non_blocking=True) for d in data]
        # compute loss
        loss = - pm.model(data[0], *data[1:]).mean()
        # update loss for history and logging
        loss_info.update(loss.detach().item() * len(data[0]), len(data[0]))
        loss_info.print_info(batch_idx, loss.item())
        # backward pass and optimizer step
        loss.backward()
        pm.optimizer.step()

    return loss_info.get_avg()


def test_epoch(pm, dataloader):
    with torch.no_grad():
        pm.model.eval()
        loss_info = dingo.core.utils.trainutils.LossInfo(pm.epoch, len(dataloader.dataset),
                                                         dataloader.batch_size, mode='Test',
                                                         print_freq=2)

        for batch_idx, data in enumerate(dataloader):
            # data to device
            data = [d.float().to(pm.device, non_blocking=True) for d in data]
            # compute loss
            loss = - pm.model(data[0], *data[1:]).mean()
            # update loss for history and logging
            loss_info.update(loss.detach().item() * len(data[0]), len(data[0]))
            loss_info.print_info(batch_idx, loss.item())

        return loss_info.get_avg()


if __name__ == '__main__':
    """
    # training
    wfd = WaveformDataset(init_args)
    pm.training_data_info = wfd.get_info()

    train_transform = wfd.get_train_transform(**pm.training_data_info)
    inference_transform = wfd.get_inference_transform(**pm.training_data_info)

    # train_loader, validation_loader = wfd.data_loader_builder(
    #     **pm.training_data_info)

    pm = PosteriorModel(model_builder, model_path)
    pm.build_inference_transform(transform_builder)
        inference_transform = train_transform(pm.training_data_info)
    pm.inference(data_dict, num_samples=100)

    pm.build_inference_transform(get_inference_transform)

    # inference
    pm.load_model(model_builder, model_path)
    inference_trafo = wfd.get_inference_transform(pm.training_data_info)
    pm.get_samples(transformation=inference_trafo)
    """
    from dingo.core.nn.nsf import create_nsf_with_rb_projection_embedding_net
    import os
    from os.path import join

    nsf_kwargs = {
        "input_dim": 4,
        "context_dim": 10,
        "num_flow_steps": 5,
        "base_transform_kwargs": {
            "hidden_dim": 64,
            "num_transform_blocks": 2,
            "activation": "elu",
            "dropout_probability": 0.0,
            "batch_norm": True,
            "num_bins": 8,
            "base_transform_type": "rq-coupling",
        },
    }
    embedding_net_kwargs = {
        'input_dims': (2, 3, 20),
        'n_rb': 10,
        'V_rb_list': None,
        'output_dim': 8,
        'hidden_dims': [32, 16, 8],
        'activation': 'elu',
        'dropout': 0.0,
        'batch_norm': True,
        'added_context': True,
    }

    tmp_dir = './tmp_files'
    os.makedirs(tmp_dir, exist_ok=True)
    model_filename = join(tmp_dir, 'model.pt')

    pm = PosteriorModel(
        model_builder=create_nsf_with_rb_projection_embedding_net,
        model_kwargs={'nsf_kwargs': nsf_kwargs,
                      'embedding_net_kwargs': embedding_net_kwargs},
    )

    optimizer_kwargs = {'type': 'adam', 'lr': 0.001}
    optimizer = utils.get_optimizer_from_kwargs(pm.model.parameters(),
                                                     **optimizer_kwargs)

    pm.save_model(model_filename)

    pm_loaded = PosteriorModel(
        model_builder=create_nsf_with_rb_projection_embedding_net,
        model_filename=model_filename,
    )

    optimizer = torch.optim.Adam(pm.model.parameters(), lr=0.0001)

    print('Done')
