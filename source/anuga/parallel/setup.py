from __future__ import division, print_function

import os
import sys

from os.path import join

#=================================================
# Code taken from pypar
#=================================================


import string
import tempfile
import shlex

def uniq_arr(arr):
    """Remove repeated values from an array and return new array."""
    ret = []
    for i in arr:
        if i not in ret:
            ret.append(i)
    return ret

def _run_command(cmd):
    import subprocess

    #print('running ' + cmd)
    try:
        #FIXME SR: The following only works for python 2.7!
        #output = subprocess.check_output(cmd, shell=True)
        #FIXME SR: This works for python 2.6
        output = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]

    except:
        output = ''

    return output
    

def _get_mpi_cmd():
    """Returns the output of the command used to compile using
    mpicc."""
    # LAM/OPENMPI/MPICH2
    output = _run_command('mpicc -show') + ' -fPIC'

    if output:
        return output

    # FIXME: If appears that MPICH actually needs these hacks.

    # MPICH
    # works with MPICH version 1.2.1 (on Debian)
    output = _run_command('mpicc -compile_info -link_info')
    if output:
        return output

    # Old version of MPICH needs this hack.
    tmp_base = tempfile.mktemp()
    tmp_c = tmp_base + ".c"
    tmp_o = tmp_base + ".o"
    tmp_file = open(tmp_c, "w")
    tmp_file.write('#include "mpi.h"\nint main(){return 0;}\n')
    tmp_file.close()
    output = _run_command("mpicc -show;"\
                          "mpicc -echo -c %s -o %s"%(tmp_c, tmp_o))
    os.remove(tmp_c)
    if os.path.exists(tmp_o):
        os.remove(tmp_o)
    if output:
        return output
    else:
        return ''


def get_mpi_flags():
    output = _get_mpi_cmd()
    print(output)
    if not output:
        if sys.platform=='win32': # From Simon Frost
            #this didn't work on my machine (Vladimir Lazunin on April 7, 2009)
            #output = "gcc -L$MPICH_DIR\SDK.gcc\lib -lmpich -I$MPICH_DIR\SDK.gcc\include"

            #"MPICH_DIR" must be set manually in environment variables
            mpi_dir = os.getenv("MPICH_DIR")
            if mpi_dir == None:
                print('MPICH_DIR environment variable must be set')
                exit()

            #for MPICH2
            sdk_prefix = mpi_dir
            lib_name = 'mpi'

            #for MPICH1
            if os.path.exists(sdk_prefix + '\\SDK'):
                sdk_prefix += '\\SDK'
                lib_name = 'mpich'
            output = 'gcc -L"%(sdk_prefix)s\lib" -l"%(lib_name)s" -I"%(sdk_prefix)s\include"' % {'sdk_prefix' : sdk_prefix, 'lib_name' : lib_name}
        else:
            output = 'cc -L/usr/opt/mpi -lmpi -lelan'


    # Now get the include, library dirs and the libs to link with.
    #flags = string.split(output)
    flags = shlex.split(output)
    flags = uniq_arr(flags) # Remove repeated values.
    inc_dirs = []
    lib_dirs = []
    libs = []
    def_macros = []
    undef_macros = []
    for f in flags:
        if f[:2] == '-I':
            inc_dirs.append(f[2:])
        elif f[:2] == '-L':
            lib_dirs.append(f[2:])
        elif f[:2] == '-l' and f[-1] != "'": # Patched by Michael McKerns July 2009
            libs.append(f[2:])
        elif f[:2] == '-U':
            undef_macros.append(f[2:])
        elif f[:2] == '-D':
            tmp = string.split(f[2:], '=')
            if len(tmp) == 1:
                def_macros.append((tmp[0], None))
            else:
                def_macros.append(tuple(tmp))
    return {'inc_dirs': inc_dirs, 'lib_dirs': lib_dirs, 'libs':libs,
            'def_macros': def_macros, 'undef_macros': undef_macros}



def configuration(parent_package='',top_path=None):
    
    from numpy.distutils.misc_util import Configuration
    from numpy.distutils.system_info import get_info
    
    mpi_flags = get_mpi_flags()
    
    print(mpi_flags)
    
    config = Configuration('parallel', parent_package, top_path)

    config.add_data_dir('test')
    config.add_data_dir('data')

    try:
        import pypar
    
        config.add_extension('mpiextras',
                         sources=['mpiextras.c'],
                         include_dirs=mpi_flags['inc_dirs'],
                         library_dirs=mpi_flags['lib_dirs'],
                         libraries=mpi_flags['libs'],
                         define_macros=mpi_flags['def_macros'],
                         undef_macros=mpi_flags['undef_macros'])
    except:
        #No parallel support
        pass

    
    return config
    
if __name__ == '__main__':
    from numpy.distutils.core import setup
    setup(configuration=configuration)


