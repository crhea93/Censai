import tensorflow as tf
from censai.models.utils import get_activation


class DownsamplingLayer(tf.keras.layers.Layer):
    def __init__(
            self,
            filters,
            kernel_size,
            activation,
            strides,
            batch_norm
    ):
        super(DownsamplingLayer, self).__init__()

        self.conv = tf.keras.layers.Conv2D(
            filters=filters,
            kernel_size=kernel_size,
            strides=strides,
            padding="SAME",
            data_format="channels_last"
        )
        self.batch_norm = tf.keras.layers.BatchNormalization() if batch_norm else tf.keras.layers.Lambda(lambda x, training=True: x)
        self.activation = activation

    def call(self, x, training=True):
        x = self.conv(x, training=training)
        x = self.batch_norm(x, training=training)
        x = self.activation(x)
        return x


class ConvEncodingLayer(tf.keras.layers.Layer):
    def __init__(
            self,
            kernel_size=3,
            downsampling_kernel_size=None,
            downsampling_filters=None,
            filters=32,
            conv_layers=2,
            activation="linear",
            batch_norm=False,
            dropout_rate=None,
            name=None,
            strides=2,
    ):
        super(ConvEncodingLayer, self).__init__(name=name)
        if downsampling_kernel_size is None:
            self.downsampling_kernel_size = kernel_size
        else:
            self.downsampling_kernel_size = tuple([downsampling_kernel_size]*2)
        if downsampling_filters is None:
            self.downsampling_filters = filters
        else:
            self.downsampling_filters = downsampling_filters
        self.kernel_size = (kernel_size,)*2 if isinstance(kernel_size, int) else kernel_size
        self.num_conv_layers = conv_layers
        self.filters = filters
        self.strides = tuple([strides]*2) if isinstance(strides, int) else strides
        self.activation = get_activation(activation)

        self.conv_layers = []
        self.batch_norms = []
        for i in range(self.num_conv_layers):
            self.conv_layers.append(
                tf.keras.layers.Conv2D(
                    filters=self.filters,
                    kernel_size=self.kernel_size,
                    padding="SAME",
                    data_format="channels_last",
                )
            )
            if batch_norm:
                self.batch_norms.append(
                    tf.keras.layers.BatchNormalization()
                )
            else:
                self.batch_norms.append(
                    tf.keras.layers.Lambda(lambda x, training=True: x)
                )
        self.downsampling_layer = DownsamplingLayer(
            filters=self.downsampling_filters,
            kernel_size=self.downsampling_kernel_size,
            activation=self.activation,
            strides=self.strides,
            batch_norm=batch_norm
        )

        if dropout_rate is None:
            self.dropout = tf.keras.layers.Lambda(lambda x, training=True: x)
        else:
            self.dropout = tf.keras.layers.SpatialDropout2D(rate=dropout_rate, data_format="channels_last")

    def call(self, x, training=True):
        for i, layer in enumerate(self.conv_layers):
            x = layer(x, training=training)
            x = self.batch_norms[i](x, training=training)
            x = self.activation(x, training=training)
            x = self.dropout(x, training=training)
        x = self.downsampling_layer(x, training=training)
        return x

    def call_with_skip_connection(self, x, training=True):
        for i, layer in enumerate(self.conv_layers):
            x = layer(x, training=training)
            x = self.batch_norms[i](x, training=training)
            x = self.activation(x)
            x = self.dropout(x, training=training)
        x_down = self.downsampling_layer(x, training=training)
        return x, x_down
