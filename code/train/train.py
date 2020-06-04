import torch
from tqdm.notebook import tqdm
import numpy as np
import wandb
import os
import gc


class Trainer(object):
    
    def __init__(self,model,criterion, optimizer,  train_loader, val_loader, n_epochs, model_dir, device):
        self.device = device
        self.model = model.to(device)
        self.optimizer = optimizer
        self.criterion = criterion
        self.train_loader = train_loader
        self.val_loader = val_loader
        ### Training and validation ###
        self.loss_history = {'training': [], 'validation': []}
        self.acc_history = {'training': [], 'validation': []}
        self.n_epochs = n_epochs
        self.model_dir = model_dir
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)


    def train(self,loss_history,acc_history):
        self.loss_history['training'].append(0)
        self.acc_history['training'].append(0)
        
        for batch_idx, (images, targets) in tqdm(enumerate(self.train_loader), total=len(self.train_loader), desc="#train_batches", leave=False):
            self.model.train()
            self.optimizer.zero_grad()

            images = images.float().to(self.device)
            targets = targets.float().to(self.device)

            predictions = self.model(images)
            loss = self.criterion(predictions, targets)
            loss.backward()

            self.optimizer.step()

            #Accuracy
            accuracy_predictions = (torch.sigmoid(predictions.detach().cpu())>0.5).float()
            correct = (accuracy_predictions == targets.detach().cpu()).float().sum()/accuracy_predictions.shape[0]

            self.loss_history['training'][-1] += float(loss.detach().cpu().data)
            self.acc_history['training'][-1] += float(correct)

        # Garbage collection
        del images, targets; gc.collect()
        torch.cuda.empty_cache()

        self.loss_history['training'][-1] /= batch_idx + 1
        self.acc_history['training'][-1] /= batch_idx + 1
    
    def validate(self,loss_history,acc_history):
        loss_history['validation'].append(0)
        acc_history['validation'].append(0)

        for batch_idx, (images, targets) in tqdm(enumerate(self.val_loader), total=len(self.val_loader), desc="#test_batches", leave=False):
            self.model.eval()

            images = images.float().to(self.device)
            targets = targets.float().to(self.device)

            predictions = self.model(images)
            loss = self.criterion(predictions, targets)

            #Accuracy
            accuracy_predictions = (torch.sigmoid(predictions.detach().cpu())>0.5).float()
            correct = (accuracy_predictions == targets.detach().cpu()).float().sum()/accuracy_predictions.shape[0]

            loss_history['validation'][-1] += float(loss.detach().cpu().data)
            acc_history['validation'][-1] += float(correct)

         # Garbage collection
        del images, targets; gc.collect()
        torch.cuda.empty_cache()

        loss_history['validation'][-1] /= batch_idx + 1
        acc_history['validation'][-1] /= batch_idx + 1


    def train_and_validate(self):
        print(f'Running {self.model.name}')
        best_val_loss = 9999999

        for epoch in tqdm(range(self.n_epochs), desc="#epochs"):
            self.train(self.loss_history, self.acc_history)

            self.validate(self.loss_history, self.acc_history)
            
            if self.loss_history['validation'][-1] < best_val_loss:
                best_val_loss = self.loss_history['validation'][-1]
                torch.save(self.model.state_dict(), '{:s}/{:s}_{:03d}.npz'.format(self.model_dir, self.model.name, epoch))

            wandb.log({"Training Loss":self.loss_history['training'][-1],
                       "Training Accuracy":self.acc_history['training'][-1],
                       "Validation Loss":self.loss_history['validation'][-1],
                       "Validation Accuracy":self.acc_history['validation'][-1]})

            print('epoch: {:3d} / {:03d}, training loss: {:.4f}, validation loss: {:.4f}, training accuracy: {:.3f}, validation accuracy: {:.3f}.'\
                .format(epoch + 1, self.n_epochs, self.loss_history['training'][-1], self.loss_history['validation'][-1], self.acc_history['training'][-1], self.acc_history['validation'][-1]))
            np.savez('{:s}/{:s}_loss_history_{:03d}.npz'.format(self.model_dir, self.model.name, epoch), self.loss_history)