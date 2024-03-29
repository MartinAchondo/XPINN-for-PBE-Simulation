import numpy as np
import tensorflow as tf


class XPINN_NeuralNet(tf.keras.Model):

    def __init__(self, hyperparameters, **kwargs):
        super().__init__(name='XPINN_NN', **kwargs)
        param_1, param_2 = hyperparameters
        self.NNs = [NeuralNet(**param_1, name='Molecule_NN'), NeuralNet(**param_2, name='Solvent_NN')]

    def call(self, X, flag):
        outputs = tf.zeros([tf.shape(X)[0], 2])   
        if flag == 'molecule':
            output = self.NNs[0](X)
            outputs = tf.concat([output, tf.zeros_like(output)], axis=1)
        elif flag == 'solvent':
            output = self.NNs[1](X)
            outputs = tf.concat([tf.zeros_like(output), output], axis=1)
        elif flag =='interface':
            outputs = tf.concat([self.NNs[0](X), self.NNs[1](X)], axis=1)
        return outputs
    
    def build_Net(self):
        self.NNs[0].build_Net()
        self.NNs[1].build_Net()


class PINN_NeuralNet(tf.keras.Model):

    def __init__(self, hyperparameters, **kwargs):
        super().__init__(name='PINN_NN', **kwargs)
        param_1, param_2 = hyperparameters
        self.NN = NeuralNet(**param_1, name='NN')
        self.NNs = [self.NN,self.NN]

    def call(self, X, flag):
        output = self.NN(X)
        outputs = tf.concat([output, output], axis=1)
        return outputs
    
    def build_Net(self):
        self.NN.build_Net()


class NeuralNet(tf.keras.Model):

    def __init__(self, 
                 input_shape=(None, 3),
                 output_dim=1,
                 num_hidden_layers=2,
                 num_neurons_per_layer=20,
                 num_hidden_blocks=2,
                 activation='tanh',
                 adaptative_activation=False,
                 kernel_initializer='glorot_normal',
                 architecture_Net='FCNN',
                 fourier_features=False, 
                 num_fourier_features=128, 
                 fourier_sigma=1,
                 scale=([-1.,-1.,-1.],[1.,1.,1.]),
                 **kwargs):
        super().__init__(**kwargs)

        self.input_shape_N = input_shape
        self.num_hidden_layers = num_hidden_layers
        self.num_hidden_blocks = num_hidden_blocks
        self.output_dim = output_dim
        self.lb = tf.constant(scale[0])
        self.ub = tf.constant(scale[1])
        self.architecture_Net = architecture_Net
        self.num_fourier_features = num_fourier_features
        self.sigma = fourier_sigma
        self.use_fourier_features = fourier_features

        # Scale layer
        self.scale = tf.keras.layers.Lambda(
            lambda x: 2.0 * (x - self.lb) / (self.ub - self.lb) - 1.0, 
            name=f'scale_layer')

        # Fourier feature layer
        if self.use_fourier_features:
            self.fourier_features = tf.keras.Sequential(name=f'fourier_layer')
            self.fourier_features.add(tf.keras.layers.Dense(num_fourier_features, 
                                                          activation=None, 
                                                          use_bias=False,
                                                          trainable=False, 
                                                          kernel_initializer=tf.initializers.RandomNormal(stddev=self.sigma),
                                                          name='fourier_features'))
            class SinCosLayer(tf.keras.layers.Layer):
                def call(self, Z):
                    return tf.concat([tf.sin(2.0*np.pi*Z), tf.cos(2.0*np.pi*Z)], axis=-1)
            self.fourier_features.add(SinCosLayer(name='fourier_sincos_layer'))

        # Custom activation function
        class CustomActivation(tf.keras.layers.Layer):
            def __init__(self, units=1, adaptative_activation=False, **kwargs):
                super(CustomActivation, self).__init__(**kwargs)
                self.units = units
                self.adaptative_activation = adaptative_activation
            def build(self, input_shape):
                self.a = self.add_weight(name='a',
                                        shape=(self.units,),
                                        initializer='ones',
                                        trainable=self.adaptative_activation)
                super(CustomActivation, self).build(input_shape)
            def call(self, inputs):
                a_expanded = tf.expand_dims(self.a, axis=0) 
                activation_func = tf.keras.activations.get(activation)
                return activation_func(inputs * a_expanded)

        # FCNN architecture
        if self.architecture_Net == 'FCNN':
            self.hidden_layers = list()
            for i in range(self.num_hidden_layers):
                layer = tf.keras.layers.Dense(num_neurons_per_layer,
                                              activation=CustomActivation(units=num_neurons_per_layer,adaptative_activation=adaptative_activation),
                                              kernel_initializer=kernel_initializer,
                                              name=f'layer_{i}')
                self.hidden_layers.append(layer)

        # ResNet architecture
        elif self.architecture_Net == 'ResNet':
            self.first = tf.keras.layers.Dense(num_neurons_per_layer,
                                               activation=CustomActivation(units=num_neurons_per_layer,adaptative_activation=adaptative_activation),
                                               kernel_initializer=kernel_initializer,
                                               name=f'layer_0')
            self.hidden_blocks = list()
            self.hidden_blocks_activations = list()
            for i in range(self.num_hidden_blocks):
                block = tf.keras.Sequential(name=f"block_{i}")
                block.add(tf.keras.layers.Dense(num_neurons_per_layer,
                                                activation=CustomActivation(units=num_neurons_per_layer,adaptative_activation=adaptative_activation),
                                                kernel_initializer=kernel_initializer))
                block.add(tf.keras.layers.Dense(num_neurons_per_layer,
                                                activation=None,
                                                kernel_initializer=kernel_initializer))
                self.hidden_blocks.append(block)
                activation_layer = tf.keras.layers.Activation(activation=CustomActivation(units=num_neurons_per_layer,adaptative_activation=adaptative_activation))
                self.hidden_blocks_activations.append(activation_layer)
            
            self.last = tf.keras.layers.Dense(num_neurons_per_layer,
                                              activation=CustomActivation(units=num_neurons_per_layer,adaptative_activation=adaptative_activation),
                                              kernel_initializer=kernel_initializer,
                                              name=f'layer_1')

        # Output layer
        self.out = tf.keras.layers.Dense(output_dim, name=f'output_layer')

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
        if self.use_fourier_features:
            Z = self.fourier_features(Z) 
        for layer in self.hidden_layers:
            Z = layer(Z)
        return self.out(Z)

    def call_ResNet(self, X):
        Z = self.scale(X)
        if self.use_fourier_features:
            Z = self.fourier_features(Z)  
        Z = self.first(Z)
        for block,activation in zip(self.hidden_blocks,self.hidden_blocks_activations):
            Z = activation(block(Z) + Z)
        Z = self.last(Z)
        return self.out(Z)
    

if __name__=='__main__':
    hyperparameters = {
                'input_shape': (None,3),
                'num_hidden_layers': 2,
                'num_neurons_per_layer': 50,
                'output_dim': 1,
                'activation': 'tanh',
                'adaptative_activation': True,
                'architecture_Net': 'FCNN',
                'fourier_features': True,
                'scale': ([-1.,-1.,-1.],[1.,1.,1.])
        }
    model = XPINN_NeuralNet([hyperparameters,hyperparameters])
    model.build_Net()
    model.NNs[0].summary()
    model.NNs[1].summary()

