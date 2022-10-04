#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 17 19:07:16 2022
TODO
1- proximity for irregular plane
@author: jiedeng
"""
import numpy as np
import ase.io
import MDAnalysis as mda
from stat_lib_base import cal_inter, fit_gds_double_sided,  temporal_mass_density_proj_coarse, pbc_x, unpbc_x, count_z, \
    cal_proximity, cal_local_rho, plot_3d_interface, plot_prox_rho, _average_prox_vs_rho, fit_gds_single_sided

class GDSAnalyzer(object):
    def __init__(self,
             # ase_xyz,
             # mda_xyz,
             xyz='merge.xyz',
             mode='mass',
             nw=1, # for MgO-Fe system, we use 1, for Pv-H system, we use 2
             project_axis = 2,
             begin = 0,
             end = -1,
             step = 1,
             alpha = 2.5,
             verbose  = False,
             analyze_planar = True,
             analyze_proximity = True):
        self.xyz = xyz
        self.ase_xyz = ase.io.read(xyz,index=':') 
        self.mda_xyz = mda.Universe(xyz)
        self.mode = mode
        self.nw = nw
        self.begin =begin
        if end == -1:
            self.end = len(self.ase_xyz)
        else:
            self.end = end
        self.step = step
        self.project_axis = project_axis
        self.alpha = alpha
        self.mesh = 1
        self.level = None
        self.verbose  = verbose
        
        self.num_atom = len(self.ase_xyz[0])
        
        self.ele_atomic_number = np.unique(self.ase_xyz[0].get_atomic_numbers())
        # ele_atomic_number = np.unique(tmp.get_atomic_numbers())

        self.ele_chemical_symbol = []
        for num in self.ele_atomic_number:
            self.ele_chemical_symbol.append(ase.data.chemical_symbols[num])
        print('System:', self.ase_xyz[0].get_chemical_formula())
        
        self.ele_indices = []
        for num in self.ele_atomic_number:
            self.ele_indices.append(np.array(range(self.num_atom))[self.ase_xyz[0].get_atomic_numbers()==num])
        # h_indices      = np.array(range(num_atom))[ase_xyz[0].get_atomic_numbers()==2]  #2
        # mg_indices      = np.array(range(num_atom))[ase_xyz[0].get_atomic_numbers()==12] # mg
        # si_indices      = np.array(range(num_atom))[ase_xyz[0].get_atomic_numbers()==26] # fe
        # o_indices      = np.array(range(num_atom))[ase_xyz[0].get_atomic_numbers()==8]  # o
        self.sum_elements_counts = []
        self.sum_phase_dimension = []
        self.sum_rechi =[]
        self.sum_prox = []
        self.analyze_proximity = analyze_proximity
        if analyze_planar or self.analyze_proximity:
            self.analyze()
            self.save_sum()            
        # if analyze_planar:
        #     self.analyze()
        #     self.save_sum()
        # if analyze_proximity:
        #     self.analyze_prox()
        
    def save_sum(self):
        name = 'sum_counts_{0}_{1}.txt'.format(self.begin,self.end-1)
        fmt =  '%d    ' + '%d %d %d    '*len(self.ele_atomic_number) +'%.4f' # for each element, we have three phases
        dat = np.concatenate((np.array([range(self.begin,self.end)]).T, self.sum_elements_counts,np.array([self.sum_rechi]).T),axis=1)
        np.savetxt(name,dat,fmt=fmt,
                    header='{0} \n {3} \n {1} \n {2}'.format(self.xyz,'solid liquid interface','id '+'           '.join(self.ele_chemical_symbol) +'    chi', 'nw = {}'.format(self.nw)))   
        
        name = 'sum_dimensions_{0}_{1}.txt'.format(self.begin,self.end-1)
        fmt = '%d ' + '%.4f '*len(self.sum_phase_dimension[0]) + '%.4f'
        dat = np.concatenate((np.array([range(self.begin,self.end)]).T, self.sum_phase_dimension, np.array([self.sum_rechi]).T),axis=1)
        np.savetxt(name,dat,fmt=fmt,
                    header='{0} \n {1}'.format(self.xyz,'id,  ls, ll, lw, lx,ly,lz, z0, z1_unpbc, chi'))   
        
        if self.analyze_proximity:
            name = 'sum_proximity_{0}_{1}.txt'.format(self.begin,self.end-1)
            dat = np.concatenate((np.array([range(self.begin,self.end)]).T, self.sum_prox),axis=1)
            fmt = '%d ' + '%d %d %d    '*len(self.ele_atomic_number) +'    %.4f'*2 # for each element, we have three phases
            np.savetxt(name,dat,fmt=fmt,
                        header='{0} \n {3} \n {1} \n {2}'.format(self.xyz,'solid liquid interface','id '+'           '.join(self.ele_chemical_symbol) +'          lw      chi', 'nw = {}'.format(self.nw)))   
            
    def analyze(self):
        """
        analyze multiple frames 
    
        Parameters
        ----------
        start_index : int, 
            start index, count from 0.
        length : int
            num of frames to be analyzed.
        save :  bool, optional
            save output,. The default is True.
        name : string, optional
            output name. The default is 'stat.txt'.
    
        Returns
        -------
        None.
    
        """


        for fn in range(self.begin,self.end,self.step):
            sol_liq_inter, ls, ll, lw, lx,ly,lz, z0, z1_unpbc, redchi = self.analyze_single(fn)
            self.sum_elements_counts.append(sol_liq_inter)
            self.sum_phase_dimension.append([ls, ll, lw, lx,ly,lz, z0, z1_unpbc])
            self.sum_rechi.append(redchi)
            if self.analyze_proximity:
                self.sum_prox.append(self.out)

            
    def analyze_single(self,idx,solid_center0=-1):
        """
        analyze all species
    
        Parameters
        ----------
        idx : TYPE
            DESCRIPTION.
        ase_xyz : TYPE
            DESCRIPTION.
        mda_xyz : TYPE
            DESCRIPTION.
        project_axis : TYPE
            DESCRIPTION.
        solid_center0 : TYPE, optional
            DESCRIPTION. The default is -1.
        alpha : TYPE, optional
            DESCRIPTION. The default is 2.5.
        plot : TYPE, optional
            DESCRIPTION. The default is True.
        verbose : TYPE, optional
            DESCRIPTION. The default is False.
        debug : TYPE, optional
            DESCRIPTION. The default is False.
        assert_chi : TYPE, optional
            DESCRIPTION. The default is True.
    
        Returns
        -------
        None.
    
        """
        print('**'*25,idx,'**'*25)

        sol_liq_inter = []
        # build interface, mda_xyz does not contain cell dim info, ase_xyz cannot by used by pytim
        self.inter, k,ase_a,mda_a = cal_inter(self.ase_xyz,self.mda_xyz,idx,self.mesh, self.alpha, self.level,self.mode)
        self.k=k
        # build density map and project to target direction
        self.rho_zi,self.zi,rho_av     = temporal_mass_density_proj_coarse(self.inter,project_axis=self.project_axis,plot=self.plot_gds,level=self.level)        
        # find solid_center
        if solid_center0 <0: # if solid center is not specified, use the default value
            solid_center0 = self.zi[np.argmax(self.rho_zi)]
        for  solid_center in [solid_center0, solid_center0 -2, solid_center0+2, solid_center0-1, solid_center0+1, solid_center0-3, solid_center0+3]:
            self.zi_new,self.rho_zi_new    = pbc_x(self.zi,self.rho_zi,solid_center)
            # fit to double sided GDS function
            self.result,z0,z1,w1 = fit_gds_double_sided(self.zi_new,self.rho_zi_new,plot=self.plot_gds, verbose=self.verbose)
            # print("     result.redchi",result.redchi)
            if self.result.redchi<0.2:
                ## store the best fitting params to params
                params = self.result.params
                break
        # if params is None:  ## changing solid center is not the key, let us adjust the other initital values
        #     pass
            
        # if assert_chi:
        #     assert result.redchi<0.5        
        # choose inteface to be w 
        w = self.nw*w1  
        # ensure z0 is close to solid center
        if (z0 - solid_center) <= (z1 - solid_center):
            pass
        else:
            tmp = z0
            z0 = z1
            z1 = tmp
        dim      = ase_a.get_cell_lengths_and_angles()[self.project_axis]

        z1_unpbc = unpbc_x(z1,dim)
        
        ### solid z1, z1_unpbc
        """
        --------z0--------z1--
        unpbc
        --z1----z0------------
        
        or 
        ----z0-----z1---------
        -
        """
        for ii in range(len(self.ele_atomic_number)):
            num = self.ele_atomic_number[ii]
            indices = self.ele_indices[ii]
            ez = ase_a.positions[indices][:,self.project_axis]
            ez[ez<0]   += ez[ez<0] + dim
            ez[ez>dim] -= ez[ez>dim] - dim
            sol_ez, liq_ez = count_z(z0,z1_unpbc, ez,w,dim)
            sol_liq_inter.append(len(sol_ez))
            sol_liq_inter.append(len(liq_ez))
            sol_liq_inter.append(len(indices) - len(sol_ez)-len(liq_ez))

            # sol_liq_inter.append([len(sol_ez), len(liq_ez), len(indices) - len(sol_ez)-len(liq_ez)])

        if z0 <  z1_unpbc:
            ls,ll = dim -(z1_unpbc - z0) - w, (z1_unpbc - z0) - w
        else:
            ls, ll = z0-z1_unpbc - w, dim - (z0-z1_unpbc) - w
            
        self.lw = self.nw*w
        
        if ls <0:
            ls = 0.00001
        if ll <0:
            ll = 0.00001
        lx,ly,lz = ase_a.get_cell_lengths_and_angles()[:3]
        self.solid_center = solid_center
        self.z0 = z0
        self.z1_unpbc = z1_unpbc
        self.w = w
        
        if self.analyze_proximity:
            proximity = cal_proximity(self.inter)[0]
            selected_rho, selected_indice =cal_local_rho(self.inter)
            selected_prox = np.array(proximity)[selected_indice]
            mean_prox,mean_rho = _average_prox_vs_rho(selected_prox,selected_rho,self.inter.ngrid[0])
            result, z0, w = fit_gds_single_sided(mean_prox,mean_rho,vary_z0=False,plot=False,verbose=False)
            
            phase1 = self.inter.all_atoms.elements[tuple([proximity < -self.lw/2])]
            phase2 = self.inter.all_atoms.elements[tuple([proximity >self.lw/2])]
            interface = self.inter.all_atoms.elements[tuple([(proximity <= self.lw/2) & (proximity >= -self.lw/2)])]

            self.out = []
            for ele in self.ele_chemical_symbol:
                # out.append([len(phase2[phase2==ele]), len(phase1[phase1==ele]),  len(interface[interface==ele])])    
                self.out.append(len(phase2[phase2==ele]))
                self.out.append(len(phase1[phase1==ele]))
                self.out.append(len(interface[interface==ele]))
            self.out.append(self.lw)
            self.out.append(result.redchi)
                            
        return sol_liq_inter, ls, ll, self.lw, lx,ly,lz, z0, z1_unpbc, self.result.redchi


    
    def plot_gds(self,out='gds.png'):
        """
        Show the density profile, fitted results, and GDS location
        """
        import matplotlib.pyplot as plt
        yrange = [min(self.rho_zi)-.5, max(self.rho_zi)+.5]
        xrange = [0,max(self.zi)]
        dim = xrange[1]
        z0s = [self.z0,self.z0]
        z1s = [self.z1_unpbc,self.z1_unpbc]       
        plt.figure()
        plt.plot(self.zi, self.rho_zi,'bo')
        plt.plot(z0s,yrange,'k--')
        plt.plot(z0s+dim,yrange,'k--')
        plt.plot(z0s-dim,yrange,'k--')

        plt.plot(z1s,yrange,'k--')
        plt.plot(z1s+dim,yrange,'k--')
        plt.plot(z1s-dim,yrange,'k--')

        rho_zi_new = self.result.best_fit
        # more flexibility
        # rho_zi_new = self.result.eval(self.result.params,z=self.zi_new)
        plt.plot(self.zi_new, rho_zi_new,'k-')
        plt.plot(self.zi_new+dim,rho_zi_new,'k-')
        plt.plot(self.zi_new-dim, rho_zi_new,'k-')        
        plt.plot([self.zi_new[-1]-dim,self.zi_new[0]],[rho_zi_new[-1], rho_zi_new[0]], 'k-')
    
        plt.fill_between([self.z0-self.lw/2,self.z0+self.lw/2], [yrange[0], yrange[0]],[yrange[1], yrange[1]],color='r',alpha=0.3)
        plt.fill_between([self.z1_unpbc-self.lw/2,self.z1_unpbc+self.lw/2], [yrange[0], yrange[0]],[yrange[1], yrange[1]],color='r',alpha=0.3)
        # consider PBC
        plt.fill_between([self.z0-self.lw/2 - dim,self.z0+self.lw/2 -dim], [yrange[0], yrange[0]],[yrange[1], yrange[1]],color='r',alpha=0.3)
        plt.fill_between([self.z0-self.lw/2 + dim,self.z0+self.lw/2 +dim], [yrange[0], yrange[0]],[yrange[1], yrange[1]],color='r',alpha=0.3)
    
        plt.fill_between([self.z1_unpbc-self.lw/2-dim,self.z1_unpbc+self.lw/2-dim], [yrange[0], yrange[0]],[yrange[1], yrange[1]],color='r',alpha=0.3)
        plt.fill_between([self.z1_unpbc-self.lw/2+ dim,self.z1_unpbc+self.lw/2+ dim], [yrange[0], yrange[0]],[yrange[1], yrange[1]],color='r',alpha=0.3)
        plt.ylim(yrange)
        plt.xlim(xrange)
        plt.minorticks_on()
        plt.xlabel('z (A)')
        plt.xlabel('z ' + r'$(\mathrm{\AA})$')
        plt.ylabel(r'$\rho$'+' ' + r'$(\mathrm{g}/\mathrm{cm}^{3})$')
        plt.savefig(out,dpi=300,bbox_inches='tight')
