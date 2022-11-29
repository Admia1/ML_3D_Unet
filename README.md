# 3D Unet Framework

This is a Tensorflow 2 based implementation of a generic 3D-Unet.

This repo allows the creation of 3D-Unet of any structure, letting you to choose the depth of the network, the number of consecutive convolutions, the number of filters on each level, the kernel size on each level, the pooling method (AvgPooling or MaxPooling), the inclusion of dropout after pooling and concatenation, inclusion of batch normalization after convolutions or not, the padding method, the upsampling method (UpSampling or ConvTranspose) and the activation function after convolutions.

To create this network:
<p align="center">
  <img src="https://github.com/luiserrador/ml/blob/master/images/unet.png">
</p>

This is the example code:
```python
from utils.layers import *
from utils.layers_func import *

unet_model_func = create_unet3d(input_shape=[128, 128, 128, 1],
                                n_convs=2,
                                n_filters=[16, 32, 64, 128],
                                ksize=[3, 3, 3],
                                padding='same',
                                pooling='max',
                                norm='batch_norm',
                                dropout=[0.25, 0.5, 0.5],
                                upsampling=True,
                                activation='relu',
                                depth=4)
                                
# OR

unet_model = create_unet3d_class(input_shape=[128, 128, 128, 1],
                                 n_convs=2,
                                 n_filters=[16, 32, 64, 128],
                                 ksize=[3, 3, 3],
                                 padding='same',
                                 pooling='max',
                                 norm='batch_norm',
                                 dropout=[0.25, 0.5, 0.5],
                                 upsampling=True,
                                 activation='relu',
                                 depth=4)
```

The difference between these two methods is that *create_unet3d* will return a model with all the Tensorflow layers that compose the U-Net, while the *create_unet3d_class* will return a model with only 1 layer, which contains the U-Net structure. For more examples, visit [examples](https://github.com/luiserrador/ml/blob/master/examples).
