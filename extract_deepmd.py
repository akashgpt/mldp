#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun 21 13:51:58 2020
merge to 
@author: jiedeng
"""
from shared_functions import load_paths
import os
import argparse
from dpdata import LabeledSystem
import glob
import numpy as np


parser = argparse.ArgumentParser()
parser.add_argument("--inputpath","-ip",help="input path file")
parser.add_argument("--batchsize","-bs",type = int, help="input path file")
parser.add_argument("--OUTCAR","-o",type = str, default = 'OUTCAR', help="OUTCAR name")
parser.add_argument("--deepmd","-d",type = str, default = 'deepmd', help="deepmd folder name")

args   = parser.parse_args()

cwd    = os.getcwd()
if args.inputpath:
    print("Check files in {0}  ".format(args.inputpath))
    inputpath = args.inputpath
    tmp = load_paths(inputpath)
    if isinstance(tmp[0],list):
        paths = []
        for i in range(len(tmp[2])):
            if tmp[1][i] >0: # only keep relax > 0
                paths.append(os.path.join(tmp[2][i],'recal'))
    else:
        paths = [os.path.join(path,'recal') for path in tmp]

else:
    print("No folders point are provided. Use default value folders")
    inputpath = os.path.join(cwd)
    paths = [cwd]

def extract_sigma_outcar(outcar):

    """
    check if INCAR temperature setting correct
    return the correct incar file
    
    """
    outcar_file = open(outcar)
    for _ in range(1000000):
        line = outcar_file.readline()
        if 'SIGMA' in line:
            sigma = float(line.split('SIGMA')[1].split('=')[1].split()[0])
            outcar_file.close()
            return sigma
        
def build_fparam(path, outcar, deepmd): # deepmd/..
#    kb = 8.617333262e-5
#    incar = os.path.join(subfolders[0],'INCAR')
    sigma = extract_sigma_outcar(outcar)
    sets=glob.glob(deepmd+"/set*")
    for seti in sets:
        energy=np.load(seti+'/energy.npy')
        size = energy.size
        all_te = np.ones(size)*sigma
        np.save( os.path.join(seti,'fparam.npy'), all_te)

def check_deepmd(path,nsw,outcar,deepmd):
    build_deepmd(path,nsw,outcar,deepmd)
    build_fparam(path, outcar, deepmd)

def best_size(tot):
    tot = int(tot)
    diff = 100000  # a very large value
    for j in range(3,6):## to be 3, 4, 5 parts
        if tot%j == 0 :
            tmp = 0
        else:
            tmp = tot//j - tot%( tot//j )
        print(tmp)
        if tmp < diff:
            diff = tmp
            size = tot//j
    return size,diff

def build_deepmd(path,nsw,outcar,deepmd):
    ls = LabeledSystem(outcar,fmt='outcar')
    deepmd = os.path.join(path,deepmd)
    if args.batchsize: 
        set_size = args.batchsize
    else:
        if nsw <= 4: # we know nsw must > 100
            set_size = 1
            print("{0} has only {1}".format(path,nsw))
        if nsw > 4:
            set_size,_ = best_size(nsw)  # 25% used as , but if say 82, then 20, 20, 20, 2, too less
    ls.to_deepmd_npy(deepmd,set_size=set_size)


def extract_nsw_outcar(outcar):

    """
    check if INCAR temperature setting correct
    return the correct incar file
    
    """
    outcar_file = open(outcar)
    nsw = 0
    for _ in range(100000000):
        line = outcar_file.readline()
        if 'nsw_tot' in line:
            nsw = float(line.split('=')[1].split()[0])
            outcar_file.close()
            return nsw
        elif 'free  energy   TOTEN' in line:
            nsw += 1
    return nsw

for path in paths:
    print(path)
    if os.path.exists(os.path.join(path,args.deepmd)):
        print("deepmd foler already exist=> skip")
    elif not os.path.exists(os.path.join(path,args.OUTCAR)):
        print("OUTCAR folder do not exists")
    else: # has required OUTCAR folder but no deepmd 
        print("Build {0}".format(args.deepmd))
        nsw =extract_nsw_outcar(os.path.join(path,args.OUTCAR))
        check_deepmd(path,nsw,os.path.join(path,args.OUTCAR), os.path.join(path,args.deepmd))
