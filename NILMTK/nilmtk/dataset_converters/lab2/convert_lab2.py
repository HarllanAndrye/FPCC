from __future__ import print_function, division
import pandas as pd
import numpy as np
from os.path import join, isdir, isfile, dirname, abspath
from os import getcwd
from sys import getfilesystemencoding
from nilmtk.datastore import Key
from nilmtk.measurement import LEVEL_NAMES
from nilmtk.utils import check_directory_exists, get_datastore
from nilm_metadata import convert_yaml_to_hdf5
from inspect import currentframe, getfile, getsourcefile
from copy import deepcopy

def reindex_fill_na(df, idx):
    df_copy = deepcopy(df)
    df_copy = df_copy.reindex(idx)

    power_columns = [
        x for x in df.columns if x[0] in ['power']]
    non_power_columns = [x for x in df.columns if x not in power_columns]

    for power in power_columns:
        df_copy[power].fillna(0, inplace=True)
    for measurement in non_power_columns:
        df_copy[measurement].fillna(
            df[measurement].median(), inplace=True)

    return df_copy


column_mapping = {
    'W': ('power', 'active'),
    'VAR': ('power', 'reactive')
}

TIMESTAMP_COLUMN_NAME = "timestamp"
TIMEZONE = "America/Fortaleza"
START_DATETIME, END_DATETIME = '6-26-2015 03:00:00', '7-4-2015 02:59:58'
FREQ = "1S"


def convert_lab2(dataset_path, output_filename, format="HDF"):
    """
    Parameters
    ----------
    dataset_path : str
        The root path of the dataset.
    output_filename : str
        The destination filename (including path and suffix).
    """

    check_directory_exists(dataset_path)
    idx = pd.DatetimeIndex(start=START_DATETIME, end=END_DATETIME, freq=FREQ)
    idx = idx.tz_localize('GMT').tz_convert(TIMEZONE)

    # Open data store
    store = get_datastore(output_filename, format, mode='w')
    electricity_path = join(dataset_path, "electricity")

    # Mains data
    for chan in range(1, 5):
        key = Key(building=1, meter=chan)
        filename = join(electricity_path, "%d.csv" % chan)
        print('Loading ', chan)
        df = pd.read_csv(filename)
        df.drop_duplicates(subset=["timestamp"], inplace=True)
        df.index = pd.to_datetime(df.timestamp.values, unit='s', utc=True)
        df = df.tz_convert(TIMEZONE)
        df = df.drop(TIMESTAMP_COLUMN_NAME, 1)
        df.rename(columns=lambda x: column_mapping[x], inplace=True)
        df.columns.set_names(LEVEL_NAMES, inplace=True)
        df = df.convert_objects(convert_numeric=True)
        df = df.dropna()
        df = df.astype(np.float32)
        df = df.sort_index()
        df = df.resample("1S")
        df = reindex_fill_na(df, idx)
        assert df.isnull().sum().sum() == 0
        store.put(str(key), df)
    store.close()
    convert_yaml_to_hdf5(join(_get_module_directory(), 'metadata'),
                         output_filename)

    print("Done converting LAB to HDF5!")


def _get_module_directory():
    path_to_this_file = dirname(getfile(currentframe()))
    if not isdir(path_to_this_file):
        encoding = getfilesystemencoding()
        path_to_this_file = dirname(unicode(__file__, encoding))
    if not isdir(path_to_this_file):
        abspath(getsourcefile(lambda _: None))
    if not isdir(path_to_this_file):
        path_to_this_file = getcwd()
    assert isdir(path_to_this_file), path_to_this_file + ' is not a directory'
    return path_to_this_file
