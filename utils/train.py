import os.path
import time
import os

import tensorflow as tf
import numpy as np

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # Comment to use GPU


class Trainer:
    """ Generic trainer:
    Upsample Blocks followed by a ConvBlock (last convolution)

    Parameters
    -----------
    n_convs : scalar
        Number of convolutions
    n_filters : scalar
        Number os filters
    ksize : scalar or tuple of scalars
        Kernel size
    padding : str
        Padding parameter as on Tensorflow ('same', 'valid', ...)
    activation : str or None
        Activation parameter as on Tensorflow ('relu', 'linear', ...)
    norm : str or None
        Normalization method - choose 'batch_norm'
    dropout : float
        Dropout rate to be applied after upsampling/deconvolution (float between 0.0 and 1.0)
    depth : scalar
        Depth level on U-net
    upsampling : boolean
        Whether to use UpSampling (True) or Conv3DTranspose (False)
    id : str
        'encoder' or 'decoder' to identify compression and extension paths
    """

    def __init__(self, model, optimizer, learning_rate, model_dir):

        self.model = model

        with tf.distribute.get_strategy().scope():
            self.train_accuracy = tf.keras.metrics.Sum()
            self.valid_accuracy = tf.keras.metrics.Sum()
            self.train_loss = tf.keras.metrics.Sum()
            self.valid_loss = tf.keras.metrics.Sum()

            self.optimizer = optimizer(learning_rate=learning_rate)

            ckpt = tf.train.Checkpoint(optimizer=self.optimizer, net=self.model)
            self.manager = tf.train.CheckpointManager(ckpt, model_dir, max_to_keep=3)
            ckpt.restore(self.manager.latest_checkpoint)

        check_dir = os.path.exists(model_dir)
        if not check_dir:
            os.makedirs(model_dir)

        self.step_dir = os.path.join(model_dir, "step.npy")
        self.model_dir = model_dir

        if self.manager.latest_checkpoint:
            print("Restored from {}".format(self.manager.latest_checkpoint))
            self.step = np.load(self.step_dir)
        else:
            print("Initializing from scratch.")
            self.step = 0

    def train(self, train_ds, valid_ds, train_size, validation_size, loss_fn, accuracy_fn, BATCH_SIZE, EPOCHS, save_step=1):

        self.EPOCHS = EPOCHS

        self.loss_fn = loss_fn
        self.accuracy_fn = accuracy_fn

        self.STEPS_PER_CALL = STEPS_PER_EPOCH = train_size // BATCH_SIZE
        self.VALIDATION_STEPS_PER_CALL = validation_size // BATCH_SIZE
        self.epoch = self.step // STEPS_PER_EPOCH
        epoch_steps = 0
        epoch_start_time = time.time()

        history = {'loss': [], 'val_loss': [], 'acc': [], 'val_acc': []}

        train_data_iter = iter(train_ds)
        valid_data_iter = iter(valid_ds)

        if self.epoch < self.EPOCHS:

            while True:
                # run training step
                print('\nEPOCH {:d}/{:d}'.format(self.epoch + 1, self.EPOCHS))
                print('Starting Training')
                self.train_step(train_data_iter)
                epoch_steps += self.STEPS_PER_CALL
                self.step += self.STEPS_PER_CALL
                print(epoch_steps, '/', STEPS_PER_EPOCH)

                # validation run at the end of each epoch
                if (self.step // STEPS_PER_EPOCH) > self.epoch:
                    print('Starting Validation')
                    # validation run
                    valid_epoch_steps = 0
                    self.valid_step(valid_data_iter)
                    valid_epoch_steps += self.VALIDATION_STEPS_PER_CALL

                    # compute metrics
                    history['acc'].append(self.train_accuracy.result().numpy() / (BATCH_SIZE * epoch_steps))
                    history['val_acc'].append(self.valid_accuracy.result().numpy() / (BATCH_SIZE * valid_epoch_steps))
                    history['loss'].append(self.train_loss.result().numpy() / (BATCH_SIZE * epoch_steps))
                    history['val_loss'].append(self.valid_loss.result().numpy() / (BATCH_SIZE * valid_epoch_steps))

                    # report metrics
                    epoch_time = time.time() - epoch_start_time
                    print('time: {:0.1f}s'.format(epoch_time),
                          'loss: {:0.4f}'.format(history['loss'][-1]),
                          'acc: {:0.4f}'.format(history['acc'][-1]),
                          'val_loss: {:0.4f}'.format(history['val_loss'][-1]),
                          'val_acc: {:0.4f}'.format(history['val_acc'][-1]))

                    print('Saving Model')
                    if save_step and self.epoch % save_step == 0:
                        model_path = (os.path.join(self.model_dir, 'model_epoch_%s.h5' % (self.epoch + 1)))
                    self.model.save(model_path)
                    self.manager.save()
                    np.save(self.step_dir, self.step)

                    # set up next epoch
                    self.epoch = self.step // STEPS_PER_EPOCH
                    epoch_steps = 0
                    epoch_start_time = time.time()
                    self.train_accuracy.reset_states()
                    self.valid_accuracy.reset_states()
                    self.valid_loss.reset_states()
                    self.train_loss.reset_states()
                    if self.epoch >= self.EPOCHS:
                        print('Training done, {} epoch'.format(self.epoch))
                        break
        else:
            print('\nAlready trained!')

    @tf.function
    def train_step(self, data_iter):
        def train_step_fn(images, labels):
            with tf.GradientTape() as tape:
                probabilities = self.model(images, training=True)
                loss = self.loss_fn(tf.cast(labels, tf.float32), probabilities)
            grads = tape.gradient(loss, self.model.trainable_variables)
            self.optimizer.apply_gradients(zip(grads, self.model.trainable_variables))
            accuracy = self.accuracy_fn(tf.cast(labels, tf.float32), probabilities)
            self.train_accuracy.update_state(accuracy)
            # train_binary_accuracy.update_state(labels, probabilities)
            self.train_loss.update_state(loss)

        for _ in tf.range(self.STEPS_PER_CALL):
            tf.distribute.get_strategy().run(train_step_fn, next(data_iter))

    @tf.function
    def valid_step(self, data_iter):
        def valid_step_fn(images, labels):
            probabilities = self.model(images, training=False)
            loss = self.loss_fn(tf.cast(labels, tf.float32), probabilities)
            accuracy = self.accuracy_fn(tf.cast(labels, tf.float32), probabilities)
            self.valid_accuracy.update_state(accuracy)
            self.valid_loss.update_state(loss)
        for _ in tf.range(self.VALIDATION_STEPS_PER_CALL):
            tf.distribute.get_strategy().run(valid_step_fn, next(data_iter))
