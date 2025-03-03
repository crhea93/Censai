import tensorflow as tf
from censai.data.lenses_tng import decode_all
from censai.utils import _bytes_feature, _int64_feature, _float_feature
import os, glob
import numpy as np
import math, time

# total number of slurm workers detected
# defaults to 1 if not running under SLURM
N_WORKERS = int(os.getenv('SLURM_ARRAY_TASK_COUNT', 1))

# this worker's array index. Assumes slurm array job is zero-indexed
# defaults to zero if not running under SLURM
THIS_WORKER = int(os.getenv('SLURM_ARRAY_TASK_ID', 0)) ## it starts from 1!!


def distributed_strategy(args):
    files = [glob.glob(os.path.join(args.dataset, "*.tfrecords"))]
    # Read concurrently from multiple records
    files = tf.data.Dataset.from_tensor_slices(files).shuffle(len(files), reshuffle_each_iteration=False)
    dataset = files.interleave(lambda x: tf.data.TFRecordDataset(x, compression_type=args.compression_type),
                               block_length=1, num_parallel_calls=tf.data.AUTOTUNE)
    total_items = int(np.sum(np.loadtxt(os.path.join(args.dataset, "shard_size.txt")), axis=0)[1])
    train_items = math.floor(args.train_split * total_items)

    dataset = dataset.shuffle(args.buffer_size, reshuffle_each_iteration=False).map(decode_all)
    train_dataset = dataset.take(train_items)
    val_dataset = dataset.skip(train_items)

    if THIS_WORKER > 1:
        time.sleep(3)
    train_dir = args.dataset + "_train"
    if not os.path.isdir(train_dir):
        os.mkdir(train_dir)
    val_dir = args.dataset + "_val"
    if not os.path.isdir(val_dir):
        os.mkdir(val_dir)
    if THIS_WORKER <= 1:
        with open(os.path.join(train_dir, "dataset_size.txt"), "w") as f:
            f.write(f"{train_items:d}")
        with open(os.path.join(val_dir, "dataset_size.txt"), "w") as f:
            f.write(f"{total_items-train_items:d}")
    options = tf.io.TFRecordOptions(compression_type=args.compression_type)
    train_shards = train_items // args.examples_per_shard + 1 * (train_items % args.examples_per_shard > 0)
    val_shards = (total_items - train_items) // args.examples_per_shard + 1 * ((total_items - train_items) % args.examples_per_shard > 0)

    for shard in range((THIS_WORKER - 1), train_shards, N_WORKERS):
        data = train_dataset.skip(shard * args.examples_per_shard).take(args.examples_per_shard)
        with tf.io.TFRecordWriter(os.path.join(train_dir, f"data_{shard:02d}.tfrecords"), options=options) as writer:
            for example in data:
                features = {
                    "kappa": _bytes_feature(example["kappa"].numpy().tobytes()),
                    "source": _bytes_feature(example["source"].numpy().tobytes()),
                    "lens": _bytes_feature(example["lens"].numpy().tobytes()),
                    "z source": _float_feature(example["z source"].numpy()),
                    "z lens": _float_feature(example["z lens"].numpy()),
                    "image fov": _float_feature(example["image fov"].numpy()),  # arc seconds
                    "kappa fov": _float_feature(example["kappa fov"].numpy()),  # arc seconds
                    "source fov": _float_feature(example["source fov"].numpy()),  # arc seconds
                    "src pixels": _int64_feature(example["source"].shape[0]),
                    "kappa pixels": _int64_feature(example["kappa"].shape[0]),
                    "pixels": _int64_feature(example["lens"].shape[0]),
                    "noise rms": _float_feature(example["noise rms"].numpy()),
                    "psf": _bytes_feature(example["psf"].numpy().tobytes()),
                    "psf pixels": _int64_feature(example["psf"].shape[0]),
                    "fwhm": _float_feature(example["fwhm"].numpy())
                }
                serialized_output = tf.train.Example(features=tf.train.Features(feature=features))
                record = serialized_output.SerializeToString()
                writer.write(record)
    for shard in range((THIS_WORKER - 1), val_shards, N_WORKERS):
        data = val_dataset.skip(shard * args.examples_per_shard).take(args.examples_per_shard)
        with tf.io.TFRecordWriter(os.path.join(val_dir, f"data_{shard:02d}.tfrecords"), options=options) as writer:
            for example in data:
                features = {
                    "kappa": _bytes_feature(example["kappa"].numpy().tobytes()),
                    "source": _bytes_feature(example["source"].numpy().tobytes()),
                    "lens": _bytes_feature(example["lens"].numpy().tobytes()),
                    "z source": _float_feature(example["z source"].numpy()),
                    "z lens": _float_feature(example["z lens"].numpy()),
                    "image fov": _float_feature(example["image fov"].numpy()),  # arc seconds
                    "kappa fov": _float_feature(example["kappa fov"].numpy()),  # arc seconds
                    "source fov": _float_feature(example["source fov"].numpy()),  # arc seconds
                    "src pixels": _int64_feature(example["source"].shape[0]),
                    "kappa pixels": _int64_feature(example["kappa"].shape[0]),
                    "pixels": _int64_feature(example["lens"].shape[0]),
                    "noise rms": _float_feature(example["noise rms"].numpy()),
                    "psf": _bytes_feature(example["psf"].numpy().tobytes()),
                    "psf pixels": _int64_feature(example["psf"].shape[0]),
                    "fwhm": _float_feature(example["fwhm"].numpy())
                }
                serialized_output = tf.train.Example(features=tf.train.Features(feature=features))
                record = serialized_output.SerializeToString()
                writer.write(record)


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Path to dataset")
    parser.add_argument("--compression_type",   default="GZIP")
    parser.add_argument("--train_split", default=0.9, type=float, help="Fraction of the dataset in the training set")
    parser.add_argument("--buffer_size", default=10000, type=int)
    parser.add_argument("--examples_per_shard", default=10000,  type=int,       help="Number of example to store in a single shard")

    args = parser.parse_args()

    distributed_strategy(args)
