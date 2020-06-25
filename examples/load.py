import glob
import numpy as np
import os

import netCDF4 as nc4

from torch.utils.data import Dataset

radiances = ['ev_250_aggr1km_refsb_1', 'ev_250_aggr1km_refsb_2', 'ev_1km_emissive_29', 'ev_1km_emissive_33', 'ev_1km_emissive_34', 'ev_1km_emissive_35', 'ev_1km_emissive_36', 'ev_1km_refsb_26', 'ev_1km_emissive_27', 'ev_1km_emissive_20', 'ev_1km_emissive_21', 'ev_1km_emissive_22', 'ev_1km_emissive_23']
coordinates = ['latitude', 'longitude']
properties = ['cloud_water_path', 'cloud_optical_thickness', 'cloud_effective_radius', 'cloud_phase_optical_properties', 'cloud_top_pressure', 'cloud_top_height', 'cloud_top_temperature', 'cloud_emissivity', 'surface_temperature']
rois = 'cloud_mask'
labels = 'cloud_layer_type'

# ------------------------------------------------------------ CUMULO HELPERS

def get_class_occurrences(labels):
    """ 
    Takes in a numpy.ndarray of size (nb_instances, W, H, nb_layers=10) describing for each pixel the types of clouds identified at each of the 10 heights and returns a numpy.ndarray of size (nb_points, 8) counting the number of times one of the 8 type of clouds was spotted vertically over a whole instance.
    The height information is then lost. 
    """
    
    occurrences = np.zeros((labels.shape[0], 8))
    
    for occ, lab in zip(occurrences, labels):

        values, counts = np.unique(lab, return_counts=True)

        for v, c in zip(values, counts):
            
            if v > -1: # unlabeled pixels are marked with -1, ignore them
                occ[v] = c
    
    return occurrences  

def get_most_frequent_label(labels):
    """ labels should be of size (nb_instances, ...).

        Returns the most frequent label for each whole instance.
    """

    label_occurrences = get_class_occurrences(labels)

    labels = np.argmax(label_occurrences, 1).astype(float)
    
    # set label of pixels with no occurences of clouds to NaN
    labels[np.sum(label_occurrences, 1) == 0] = np.NaN

    return labels

def read_nc(nc_file):
    """return masked arrays, with masks indicating the invalid values"""
    
    file = nc4.Dataset(nc_file, 'r', format='NETCDF4')

    f_radiances = np.vstack([file.variables[name][:] for name in radiances])
    f_properties = np.vstack([file.variables[name][:] for name in properties])
    f_rois = file.variables[rois][:]
    f_labels = file.variables[labels][:]

    return f_radiances, f_properties, f_rois, f_labels

def read_npz(npz_file):

    file = np.load(npz_file)

    return file['radiances'], file['properties'], file['cloud_mask'], file['labels']

class CumuloDataset(Dataset):

    def __init__(self, root_dir, ext="nc", label_preproc=get_most_frequent_label, normalizer=None):
        
        self.root_dir = root_dir
        self.ext = ext

        if ext not in ["nc", "npz"]:
            raise NotImplementedError("only .nc and .npz extensions are supported")

        self.file_paths = glob.glob(os.path.join(root_dir, "*." + ext))

        if len(self.file_paths) == 0:
            raise FileNotFoundError("no", ext, " files in", self.root_dir)

        self.normalizer = normalizer
        self.label_preproc = label_preproc

    def __len__(self):

        return len(self.file_paths)

    def __getitem__(self, idx):

        filename = self.file_paths[idx]

        if self.ext == "nc":
            radiances, properties, rois, labels = read_nc(filename)

        elif self.ext == "npz":
            radiances, properties, rois, labels = read_npz(filename)

        if self.normalizer is not None:
            radiances = self.normalizer(radiances)

        if self.label_preproc is not None:
            labels = self.label_preproc(labels)

        return filename, radiances, properties, rois, labels

    def __str__(self):
        return 'CUMULO'

class Normalizer(object):

    def __init__(self, mean, std):

        self.mean = mean
        self.std = std

    def __call__(self, instance):

        return (instance - self.mean) / self.std

if __name__ == "__main__":  

    load_path = "../DATA/npz/label/"

    dataset = CumuloDataset(load_path, ext="npz")

    for instance in dataset:

        filename, radiances, properties, rois, labels = instance
