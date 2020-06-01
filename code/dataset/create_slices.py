import sys
import argparse
import torch
import numpy as np
import SimpleITK as sitk
from tqdm.notebook import tqdm
import csv
import os

CARTESIUS_TRAIN_BRAINTRIAGE = "/projects/0/ismi2018/BrainTriage"

parser = argparse.ArgumentParser(description='Extract slices for train/test data.')
parser.add_argument('-o', type=str, nargs='?', dest="out_path",
                    default = "../data/", help='output directory')
parser.add_argument('--train', dest="do_train", action='store_true',
                    help='whether to extract slices for train data')
parser.add_argument('--test', dest="do_test", action='store_true',
                    help='whether to extract slices for test data')

def generate_slice_data(in_dir,out_dir, test=False):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    patients = []
    
    # Work-around for different folder structure of test data
    class_dirs = ["final_test_set"] if test else os.listdir(in_dir)
    for klass in class_dirs:
        for patient in tqdm(os.listdir(os.path.join(in_dir, klass)), desc="Patients"):
            
            ## Check if patient has not been processed yet
            if patient not in patients:
                ## Paths to the image files
                t1_path = os.path.join(in_dir, klass, patient,'T1.mha')
                t2_path = os.path.join(in_dir, klass, patient,'T2.mha')
                t2_flair_path = os.path.join(in_dir, klass, patient,'T2-FLAIR.mha')

                ## Load all images as numpy arrays
                t1_array = sitk.GetArrayFromImage(sitk.ReadImage(t1_path))
                t2_array = sitk.GetArrayFromImage(sitk.ReadImage(t2_path))
                t2_flair_array = sitk.GetArrayFromImage(sitk.ReadImage(t2_flair_path))
                
                n_slices = t1_array.shape[0]
                
                for slice_number in range(n_slices):

                    with open(out_dir+'/labels_slices.csv', 'a') as csvfile:      
                        w = csv.writer(csvfile, delimiter=',')
                        ## Write 0 if "normal", 1 if "abnormal"
                        w.writerow([patient, slice_number, klass == "abnormal"])

                    t1_slice = t1_array[slice_number,:,:]
                    t2_slice = t2_array[slice_number,:,:]
                    t2_flair_slice = t2_flair_array[slice_number,:,:]
                    comb_data = np.array([t1_slice, t2_slice, t2_flair_slice])

                    ## Save as torch tensor for quick loading during training
                    torch.save(torch.from_numpy(comb_data.astype('float32')), os.path.join(out_dir, f"{patient}_{slice_number}.pt"))
            else:
                continue
                
            patients.append(patient)

if __name__ == "__main__":
    args = parser.parse_args()

    if args.do_train:
        print("Extracting train slice data")
        generate_slice_data(os.path.join(CARTESIUS_TRAIN_BRAINTRIAGE, "train/full"), os.path.join(args.out_path, "train"))
    if args.do_test:
        print("Extracting test slice data")
        generate_slice_data(os.path.join(CARTESIUS_TRAIN_BRAINTRIAGE), os.path.join(args.out_path, "test"), test=True)
    print("Done")
