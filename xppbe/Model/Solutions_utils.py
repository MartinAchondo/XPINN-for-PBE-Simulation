import numpy as np
import tensorflow as tf
from scipy import special as sp

class Solution_utils(): 

    qe = 1.60217663e-19
    eps0 = 8.8541878128e-12     
    kb = 1.380649e-23              
    Na = 6.02214076e23
    ang_to_m = 1e-10
    to_V = qe/(eps0 * ang_to_m)  
    apbs_unit_to = kb/(qe*to_V)
    cal2j = 4.184
    T = 300

    pi = np.pi

    apbs_created = False
    pbj_created = False
    pbj_mesh_density = 5
    pbj_mesh_generator = 'msms'

    def phi_known(self,function,field,X,flag,R=None,N=20):
        r = np.linalg.norm(X, axis=1)   
           
        if function == 'Spherical_Harmonics':
            phi_values = self.Spherical_Harmonics(X, flag, R,N=N)
            if flag=='solvent':
                phi_values -= self.G(X)[:,0]
        elif function == 'G_Yukawa':
            phi_values = self.G_Yukawa(X)[:,0] - self.G(X)[:,0]
        elif function == 'analytic_Born_Ion':
            phi_values = self.analytic_Born_Ion(r, R)
        elif function == 'PBJ':
            phi_values = self.pbj_solution(X, flag)
            if flag=='solvent':
                phi_values -= self.G(X)[:,0]
        elif function == 'APBS':
            phi_values = self.apbs_solution(X)*self.apbs_unit_to*self.T
        
        if field == 'react':
            return np.array(phi_values)
        elif field == 'phi':
            return np.array(phi_values + self.G(X)[:,0])

    def G(self,X):
        r_vec_expanded = tf.expand_dims(X, axis=1)
        x_qs_expanded = tf.expand_dims(self.x_qs, axis=0)
        r_diff = r_vec_expanded - x_qs_expanded
        r = tf.sqrt(tf.reduce_sum(tf.square(r_diff), axis=2))
        q_over_r = self.qs / r
        total_sum = tf.reduce_sum(q_over_r, axis=1)
        result = (1 / (self.epsilon_1 * 4 * self.pi)) * total_sum
        result = tf.expand_dims(result, axis=1)
        return result
    
    def dG_n(self,X,n):
        r_vec_expanded = tf.expand_dims(X, axis=1)
        x_qs_expanded = tf.expand_dims(self.x_qs, axis=0)
        r_diff = r_vec_expanded - x_qs_expanded
        r = tf.sqrt(tf.reduce_sum(tf.square(r_diff), axis=2))
        dg_dr = self.qs / (r**3) * (-1 / (self.epsilon_1 * 4 * self.pi)) * (1/2)
        dx = dg_dr * 2*r_diff[:, :, 0]
        dy = dg_dr * 2*r_diff[:, :, 1]
        dz = dg_dr * 2*r_diff[:, :, 2]
        dx_sum = tf.reduce_sum(dx, axis=1)
        dy_sum = tf.reduce_sum(dy, axis=1)
        dz_sum = tf.reduce_sum(dz, axis=1)
        dg_dn = n[:, 0] * dx_sum + n[:, 1] * dy_sum + n[:, 2] * dz_sum
        return tf.reshape(dg_dn, (-1, 1))
    
    def source(self,X):
        r_vec_expanded = tf.expand_dims(X, axis=1)
        x_qs_expanded = tf.expand_dims(self.x_qs, axis=0)
        r_diff = r_vec_expanded - x_qs_expanded
        r2 = tf.reduce_sum(tf.square(r_diff), axis=2)
        delta = tf.exp((-1/(2*self.sigma**2))*r2)
        q_times_delta = self.qs*delta
        total_sum = tf.reduce_sum(q_times_delta, axis=1)
        normalizer = (1/((2*self.pi)**(3.0/2)*self.sigma**3))
        result = (-1/self.epsilon_1)*normalizer * total_sum
        result = tf.expand_dims(result, axis=1)
        return result
        
    def G_Yukawa(self,X):
        r_vec_expanded = tf.expand_dims(X, axis=1)
        x_qs_expanded = tf.expand_dims(self.x_qs, axis=0)
        r_diff = r_vec_expanded - x_qs_expanded
        r = tf.sqrt(tf.reduce_sum(tf.square(r_diff), axis=2))
        q_over_r = self.qs*tf.exp(-self.kappa*r) / r
        total_sum = tf.reduce_sum(q_over_r, axis=1)
        result = (1 / (self.epsilon_2 * 4 * self.pi)) * total_sum
        result = tf.expand_dims(result, axis=1)
        return result
        
    def analytic_Born_Ion(self,r, R=None):
        if R is None:
            R = self.mesh.R_mol
        epsilon_1 = self.epsilon_1
        epsilon_2 = self.epsilon_2
        kappa = self.kappa
        q = self.q_list[0].q

        f_IN = lambda r: (q/(4*self.pi)) * ( - 1/(epsilon_1*R) + 1/(epsilon_2*(1+kappa*R)*R) )
        f_OUT = lambda r: (q/(4*self.pi)) * (np.exp(-kappa*(r-R))/(epsilon_2*(1+kappa*R)*r) - 1/(epsilon_1*r))

        y = np.piecewise(r, [r<=R, r>R], [f_IN, f_OUT])

        return y

    def analytic_Born_Ion_du(self,r):
        rI = self.mesh.R_mol
        epsilon_1 = self.epsilon_1
        epsilon_2 = self.epsilon_2
        kappa = self.kappa
        q = self.q_list[0].q

        f_IN = lambda r: (q/(4*self.pi)) * ( -1/(epsilon_1*r**2) )
        f_OUT = lambda r: (q/(4*self.pi)) * (np.exp(-kappa*(r-rI))/(epsilon_2*(1+kappa*rI))) * (-kappa/r - 1/r**2)

        y = np.piecewise(r, [r<=rI, r>rI], [f_IN, f_OUT])

        return y


    def Spherical_Harmonics(self, x, flag, R=None, N=20):

        q = self.qs.numpy()
        xq = self.x_qs.numpy()
        E_1 = self.epsilon_1.numpy()
        E_2 = self.epsilon_2.numpy()
        kappa = self.kappa.numpy()
        if R is None:
            R = self.mesh.R_max_dist

        PHI = np.zeros(len(x))

        for K in range(len(x)):
            rho = np.sqrt(np.sum(x[K,:] ** 2))
            zenit = np.arccos(x[K, 2] / rho)
            azim = np.arctan2(x[K, 1], x[K, 0])

            phi = 0.0 + 0.0 * 1j

            for n in range(N):
                for m in range(-n, n + 1):

                    Enm = 0.0
                    for k in range(len(q)):
                        rho_k = np.sqrt(np.sum(xq[k,:] ** 2))
                        zenit_k = np.arccos(xq[k, 2] / rho_k)
                        azim_k = np.arctan2(xq[k, 1], xq[k, 0])

                        Enm += (
                            q[k]
                            * rho_k**n
                            *4*np.pi/(2*n+1)
                            * sp.sph_harm(m, n, -azim_k, zenit_k)
                        )

                    Anm = Enm * (1/(4*np.pi)) * ((2*n+1)) / (np.exp(-kappa*R)* ((E_1-E_2)*n*self.get_K(kappa*R,n)+E_2*(2*n+1)*self.get_K(kappa*R,n+1)))
                    Bnm = 1/(R**(2*n+1))*(np.exp(-kappa*R)*self.get_K(kappa*R,n)*Anm - 1/(4*np.pi*E_1)*Enm)
                    
                    if flag=='molecule':
                        phi += Bnm * rho**n * sp.sph_harm(m, n, azim, zenit)
                    if flag=='solvent':
                        phi += Anm * rho**(-n-1)* np.exp(-kappa*rho) * self.get_K(kappa*rho,n) * sp.sph_harm(m, n, azim, zenit)

            PHI[K] = np.real(phi)
        
        return PHI


    @staticmethod
    def get_K(x, n):
        K = 0.0
        n_fact = sp.factorial(n)
        n_fact2 = sp.factorial(2 * n)
        for s in range(n + 1):
            K += (
                2**s
                * n_fact
                * sp.factorial(2 * n - s)
                / (sp.factorial(s) * n_fact2 * sp.factorial(n - s))
                * x**s
            )
        return K

    def pbj_solution(self,X,flag):

        if not self.pbj_created:

            from .pbj_utils.pbj_interface import PBJ
            if hasattr(self, 'mesh'):
                self.pbj_mesh_density = self.mesh.density_mol
                self.pbj_mesh_generator = self.mesh.mesh_generator

            self.pbj_obj = PBJ(self.domain_properties,self.pqr_path,self.pbj_mesh_density,self.pbj_mesh_generator,self.results_path)
            self.pbj_phi = self.pbj_obj.simulation.solutes[0].results['phi'].coefficients.reshape(-1,1)
            self.pbj_vertices = np.array(self.pbj_obj.simulation.solutes[0].mesh.vertices).transpose()
            self.pbj_elements = np.array(self.pbj_obj.simulation.solutes[0].mesh.elements).transpose()
            self.pbj_created = True

        phi = self.pbj_obj.calculate_potential(X,flag)
        return phi

    def apbs_solution(self,X):

        if not self.apbs_created:
            from .apbs_utils.apbs_interface import APBS
            
            self.apbs_obj = APBS(self.domain_properties,self.equation,self.pqr_path,self.results_path)
            self.apbs_created = True

        phi = self.apbs_obj.calculate_potential(X)
        return phi
