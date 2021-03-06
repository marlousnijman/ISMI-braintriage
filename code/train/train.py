import torch
from tqdm import tqdm
import wandb
import os
import gc
import time


class Trainer(object):
    
    def __init__(self,model,criterion, optimizer,  train_loader, val_loader, n_epochs, model_dir, device, verbose = False):
        self.device = device
        self.model = model.to(device)
        self.optimizer = optimizer
        self.criterion = criterion
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.n_epochs = n_epochs
        self.model_dir = model_dir
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
        self.verbose = verbose


    def train(self):   
        epoch_loss, epoch_acc = 0., 0.

        epoch_start_time = batch_start_time = time.time()
        avg_component_times = {"load-batch" : 0., "forward" : 0., "backward" : 0., "metrics" : 0.}

        for batch_idx, (images, targets) in tqdm(enumerate(self.train_loader), total=len(self.train_loader), desc="#train_batches", leave=False):
            if self.verbose:
                avg_component_times["load-batch"] += time.time() - batch_start_time

            self.model.train()
            self.optimizer.zero_grad()

            images = images.float().to(self.device)
            targets = targets.float().to(self.device)

            forward_start_time = time.time()
            output = self.model(images)
            if self.verbose:
                avg_component_times["forward"] += time.time() - forward_start_time

            loss = self.criterion(output, targets)

            backward_start_time = time.time()
            loss.backward()
            if self.verbose:
                avg_component_times["backward"] += time.time() - backward_start_time

            self.optimizer.step()

            # Metrics
            metrics_start_time = time.time()
            targets = targets.detach().cpu()
            probabilities = torch.sigmoid(output.detach().cpu())
            predictions = (probabilities > 0.5).float()

            accuracy = _compute_accuracy(predictions, targets); epoch_acc += accuracy
            loss = loss.detach().cpu();                         epoch_loss += loss

            if self.verbose:
                avg_component_times["metrics"] += time.time() - metrics_start_time

            wandb.log({"Training Loss (per iteration)": loss,
                       "Training Accuracy (per iteration)": accuracy})

            batch_start_time = time.time()

        print(f"One epoch (training) took {time.time()-epoch_start_time} seconds")
        if self.verbose:
            for component in avg_component_times.keys():
                print(f"{component} took on average {avg_component_times[component] / batch_idx + 1} seconds")

        # Garbage collection
        del images, targets; gc.collect()
        torch.cuda.empty_cache()

        epoch_loss /= batch_idx + 1; epoch_acc /= batch_idx + 1

        return epoch_loss, epoch_acc
    
    def validate(self):
        epoch_loss, epoch_acc = 0., 0.

        start_time = time.time()

        for batch_idx, (images, targets) in tqdm(enumerate(self.val_loader), total=len(self.val_loader), desc="#test_batches", leave=False):
            self.model.eval()

            images = images.float().to(self.device)
            targets = targets.float().to(self.device)

            output = self.model(images)
            loss = self.criterion(output, targets)

            # Metrics
            targets = targets.detach().cpu()
            probabilities = torch.sigmoid(output.detach().cpu())
            predictions = (probabilities > 0.5).float()

            accuracy = _compute_accuracy(predictions, targets); epoch_acc += accuracy
            loss = loss.detach().cpu();                         epoch_loss += loss

            wandb.log({"Validation Loss (per iteration)": loss,
                       "Validation Accuracy (per iteration)": accuracy})

        print(f"One epoch (validation) took {time.time()-start_time} seconds")

        # Garbage collection
        del images, targets; gc.collect()
        torch.cuda.empty_cache()

        epoch_loss /= batch_idx + 1; epoch_acc /= batch_idx + 1

        return epoch_loss, epoch_acc


    def train_and_validate(self):
        print(f'Running {self.model.name}')

        best_model_file_name, best_val_acc, best_val_loss = "", 0., 999999.

        for epoch in tqdm(range(self.n_epochs), desc="#epochs"):
            train_loss, train_acc = self.train()

            val_loss, val_acc = self.validate()
            
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_val_loss = val_loss
                best_model_file_name = '{:s}/{:s}_{:03d}.pt'.format(self.model_dir, self.model.name, epoch)
                _write_best_model_file_name(best_model_file_name, self.model.name)
            elif (val_acc == best_val_acc) & (val_loss < best_val_loss):
                best_val_acc = val_acc
                best_val_loss = val_loss
                best_model_file_name = '{:s}/{:s}_{:03d}.pt'.format(self.model_dir, self.model.name, epoch)
                _write_best_model_file_name(best_model_file_name, self.model.name)

            torch.save(self.model.state_dict(), '{:s}/{:s}_{:03d}.pt'.format(self.model_dir, self.model.name, epoch))

            wandb.log({"Training Loss": train_loss,
                       "Training Accuracy": train_acc,
                       "Validation Loss": val_loss,
                       "Validation Accuracy": val_acc})


def _compute_accuracy(predictions, targets):
    return (predictions == targets).float().sum() / predictions.shape[0]

def _write_best_model_file_name(best_model_file_name, model_name):
    # Save model to tmp directory
    if not os.path.exists("tmp"):
        os.makedirs("tmp")

    # Overwrite existing file
    with open(os.path.join("tmp", model_name), 'w') as f:
        f.write(best_model_file_name)
