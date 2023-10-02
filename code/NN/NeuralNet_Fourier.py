import tensorflow as tf
import numpy as np

class NeuralNet(tf.keras.Model):

    def __init__(self, lb, ub, 
                 input_shape=(None, 3),
                 output_dim=1,
                 num_hidden_layers=2,
                 num_neurons_per_layer=20,
                 num_hidden_blocks=2,
                 activation='tanh',
                 kernel_initializer='glorot_normal',
                 architecture_Net='FCNN',
                 num_fourier_features=32,  # Number of Fourier features
                 **kwargs):
        super().__init__(**kwargs)

        self.input_shape_N = input_shape
        self.num_hidden_layers = num_hidden_layers
        self.num_hidden_blocks = num_hidden_blocks
        self.output_dim = output_dim
        self.lb = lb
        self.ub = ub
        self.architecture_Net = architecture_Net
        self.num_fourier_features = num_fourier_features

        # Scale layer
        self.scale = tf.keras.layers.Lambda(
            lambda x: 2.0 * (x - self.lb) / (self.ub - self.lb) - 1.0, 
            name=f'layer_input')

        # Fourier feature layer
        self.fourier_features = tf.keras.layers.Dense(num_fourier_features, activation=None, name='fourier_features')
        self.fourier_scale = tf.constant(2.0 * np.pi, dtype=tf.float32)  # Scaling factor for frequencies

        # FCNN architecture
        if self.architecture_Net == 'FCNN':
            self.hidden_layers = list()
            for i in range(self.num_hidden_layers):
                layer = tf.keras.layers.Dense(num_neurons_per_layer,
                                              activation=tf.keras.activations.get(activation),
                                              kernel_initializer=kernel_initializer,
                                              name=f'layer_{i}')
                self.hidden_layers.append(layer)

        # ResNet architecture
        elif self.architecture_Net == 'ResNet':
            self.first = tf.keras.layers.Dense(num_neurons_per_layer,
                                               activation=tf.keras.activations.get(activation),
                                               kernel_initializer=kernel_initializer,
                                               name=f'layer_0')
            self.hidden_blocks = list()
            for i in range(self.num_hidden_blocks):
                block = tf.keras.Sequential(name=f"block_{i}")
                block.add(tf.keras.layers.Dense(num_neurons_per_layer,
                                                activation=tf.keras.activations.get(activation),
                                                kernel_initializer=kernel_initializer))
                block.add(tf.keras.layers.Dense(num_neurons_per_layer,
                                                activation=tf.keras.activations.get(activation),
                                                kernel_initializer=kernel_initializer))
                self.hidden_blocks.append(block)
            self.last = tf.keras.layers.Dense(num_neurons_per_layer,
                                              activation=tf.keras.activations.get(activation),
                                              kernel_initializer=kernel_initializer,
                                              name=f'layer_1')

        # Output layer
        self.out = tf.keras.layers.Dense(output_dim, name=f'layer_output')

    def build_Net(self):
        self.build(self.input_shape_N)

    def call(self, X):
        if self.architecture_Net == 'FCNN':
            return self.call_FCNN(X)
        elif self.architecture_Net == 'ResNet':
            return self.call_ResNet(X)

    # Call NeuralNet functions with the desired architecture

    def call_FCNN(self, X):
        Z = self.scale(X)
        Z = self.fourier_features(Z)  # Add Fourier features here
        Z = tf.concat([tf.sin(self.fourier_scale * Z), tf.cos(self.fourier_scale * Z)], axis=-1)  # Split into sine and cosine components
        for layer in self.hidden_layers:
            Z = layer(Z)
        return self.out(Z)

    def call_ResNet(self, X):
        Z = self.scale(X)
        Z = self.fourier_features(Z)  # Add Fourier features here
        Z = tf.concat([tf.sin(self.fourier_scale * Z), tf.cos(self.fourier_scale * Z)], axis=-1)  # Split into sine and cosine components
        Z = self.first(Z)
        for block in self.hidden_blocks:
            Z = block(Z) + Z
        Z = self.last(Z)
        return self.out(Z)
