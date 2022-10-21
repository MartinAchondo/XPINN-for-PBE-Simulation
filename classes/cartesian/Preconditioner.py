import tensorflow as tf
import numpy as np


class preconditioner():

    def __init__(self):
        
        self.DTYPE='float32'
        self.pi = tf.constant(np.pi, dtype=self.DTYPE)

    def set_domain(self,X):
        x,y = X
        self.xmin = x[0]
        self.xmax = x[1]
        self.ymin = y[0]
        self.ymax = y[1]

        lb = tf.constant([self.xmin, self.ymin], dtype=self.DTYPE)
        ub = tf.constant([self.xmax, self.ymax], dtype=self.DTYPE)

        return (lb,ub)

    def fun_r(self,x,y):
        z = x**2 + y**2
        return z

    def loss_fn(self,model,mesh):
        R = mesh.stack_X(self.x,self.y)
        upred = model(R)
        u = self.fun_r(self.x,self.y)
        loss = tf.reduce_mean(tf.square(upred-u))
        return loss