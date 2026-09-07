import os
import shutil
import glob

mt5_dir = '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/MQL5'
exp_dir = os.path.join(mt5_dir, 'Experts')
adv_dir = os.path.join(exp_dir, 'Advisors')
inc_dir = os.path.join(mt5_dir, 'Include', 'QuantumTitan')

os.makedirs(adv_dir, exist_ok=True)
os.makedirs(inc_dir, exist_ok=True)

for name in ['QuantumTitan_v12_Singularity.ex5', 'QuantumTitan_v12_Singularity.mq5']:
    src = os.path.join('/home/ubuntu', name)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(exp_dir, name))
        shutil.copy2(src, os.path.join(adv_dir, name))
        print('Copied', name, '->', exp_dir)

for f in glob.glob('/home/ubuntu/QuantumTitan/*'):
    dst = os.path.join(inc_dir, os.path.basename(f))
    shutil.copy2(f, dst)
    print('Copied Include', os.path.basename(f), '->', inc_dir)

print('File deployment complete!')
