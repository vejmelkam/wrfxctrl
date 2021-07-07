# Copyright (C) 2013-2016 Martin Vejmelka, UC Denver
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR
# A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#

from __future__ import absolute_import
from __future__ import print_function
from utils import to_esmf, to_utc, rm
from datetime import datetime, timedelta
import pytz
import json
import os
import os.path as osp
import stat
from subprocess import Popen, call, check_output
import glob
import logging
import pprint

def select_grib_source(start_time):
    now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    if now - start_time < timedelta(days=30):
        return 'NAM'
    else:
        return 'NARR'

def simulation_paths(sim_id, conf):
    """
    Get paths to simulation files.
     
    :param sim_id: the simulation id
    :param conf: configuration
    """
    return {'log_path' : conf['logs_path'] + '/' + sim_id + '.log' ,
            'json_path' : conf['jobs_path'] + '/' + sim_id + '.json',
            'state_path' : conf['sims_path'] + '/' + sim_id + '.json',
            'run_script' : conf['jobs_path'] + '/' + sim_id + '.sh'}

def cancel_simulation(sim_info,conf):
    """
    Cancel simulation job. Do not delete files.
    :param sim_info: the simulation json 
    :param conf: configuration
    """
    cmd = osp.abspath(osp.join(conf['wrfxpy_path'],'cleanup.sh'))
    job_id = sim_info['job_id']
    exe = [cmd, 'cancel', job_id]
    logging.debug('Calling ' + ' '.join(exe))
    out = check_output(exe)
    logging.info(out)

    paths = simulation_paths(sim_info['id'],conf)
    log_path = paths['log_path']
    with open(log_path, 'wb') as f:
        f.write(out)
        f.write(b'Cancelled')

def cleanup_sim_output(sim_info,conf):
    """    Cleanup simulation output.
    :param sim_info: the simulation json 
    :param conf: configuration
    """
    cmd = osp.abspath(osp.join(conf['wrfxpy_path'],'cleanup.sh'))
    job_id = sim_info['job_id']
    exe = [cmd, 'output', job_id]
    logging.debug('Calling ' + ' '.join(exe))
    os.system(' '.join(exe))

def cleanup_sim_workspace(sim_info,conf):
    """    Cleanup simulation workspace.
    :param sim_info: the simulation json 
    :param conf: configuration
    """
    cmd = osp.abspath(osp.join(conf['wrfxpy_path'],'cleanup.sh'))
    job_id = sim_info['job_id']
    exe = [cmd, 'workspace', job_id]
    logging.debug('Calling ' + ' '.join(exe))
    os.system(' '.join(exe))

def delete_simulation(sim_info,conf):
    """
    Delete simulation from wrfxpy and all files.
    :param sim_info: the simulation json 
    :param conf: configuration
    """
    cmd = osp.abspath(osp.join(conf['wrfxpy_path'],'cleanup.sh'))
    job_id = sim_info['job_id']
    exe = [cmd, 'delete', job_id]
    logging.debug('Calling ' + ' '.join(exe))
    os.system(' '.join(exe))
    delete_simulation_files(sim_info['id'],conf)

def delete_simulation_files(sim_id,conf):
    """
    Remove all files for given simulation.
    :param sim_id: the simulation id
    :param conf: configuration
    """
    rm(list(simulation_paths(sim_id,conf).values()))

def load_simulations(sims_path):
    """
    Load all simulations stored in the simulations/ directory.

    :params sims_path: path to jsons with simulation states 
    :return: a dictionary of simulations
    """

    logging.info('Loading simulation states from %s' % sims_path)
    files = glob.glob(sims_path + '/*.json') 
    simulations = {}
    for f in files:
        logging.info('load_simulations: loading file %s' % f)
        try:
            sim_info = json.load(open(f))
            if 'job_id' not in sim_info:
                # older files do not have job_id, redo from the visualization link
                link=sim_info['visualization_link']
                sim_info['job_id']=link[link.find('wfc-'):]
                logging.debug('Added missing job_id ' + sim_info['job_id'])
            sim_id = sim_info['id']
            simulations[sim_id] = sim_info
            logging.info('load_simulations: loaded simulation id %s' % sim_id)
        except ValueError:
            logging.error('load_simulations: failed to reload simulation %s' % f)
            os.rename(f, f + '.error') 
    return simulations

def create_simulation(info, conf, cluster):
    """
    Build a simulation JSON configuration based on profiles and execute
    the simulation using wrfxpy.
    
    :param info: the simulation info gathered from the build page
    :param conf: configuration
    :param cluster: a cluster object that conveys information about the computing environment
    :return: the simulation info object
    """
    now = datetime.utcnow()
    sim_id = 'from-web-%04d-%02d-%02d_%02d-%02d-%02d' % (now.year, now.month, now.day, now.hour, now.minute, now.second)

    # get paths of all files created
    path= simulation_paths(sim_id,conf)
    log_path = path['log_path']
    json_path = path['json_path']
    run_script = path['run_script']

    # store simulation configuration
    profile = info['profile']
    print('profile = %s' % json.dumps(profile,indent=1, separators=(',',':')))
    ign_lat, ign_lon = float(info['ignition_latitude']), float(info['ignition_longitude'])
    # example of ignition time: Apr 10, 1975 9:45 PM
    ign_time_esmf = to_esmf(datetime.strptime(info['ignition_time'], '%b %d, %Y %I:%M %p'))
    sim_descr = info['description']
    fc_hours = int(info['fc_hours'])
    sim_info = {
      'id' : sim_id,
      'started_at' : to_esmf(datetime.now()),
      'description' : sim_descr,
      'ign_latitude' : ign_lat,
      'ign_longitude' : ign_lon,
      'ign_time_esmf' : ign_time_esmf,
      'fc_hours' : fc_hours,
      'profile' : info['profile'],
      'log_file' : log_path,
      'state' : make_initial_state()
    }

    # build a new job template
    template = osp.abspath(profile['template'])
    cfg = json.load(open(template))
    print('Job template %s:' % template)
    print(json.dumps(cfg, indent=4, separators=(',', ': ')))
    
    cfg['template'] = template
    cfg['profile'] = profile
    cfg['grid_code'] = sim_id
    cfg['num_nodes'] = cluster.nodes
    cfg['ppn'] = cluster.ppn
    ign_time = to_utc(ign_time_esmf)
    sim_start = (ign_time - timedelta(minutes=30)).replace(minute=0, second=0)
    sim_end = sim_start + timedelta(hours=fc_hours)
    sim_info['start_utc'] = to_esmf(sim_start)
    sim_info['end_utc'] = to_esmf(sim_end)
    cfg['start_utc'] = to_esmf(sim_start)
    cfg['end_utc'] = to_esmf(sim_end)
    if 'grib_source' not in cfg or cfg['grib_source'] == 'auto':
        cfg['grib_source'] = select_grib_source(sim_start)
        print('GRIB source not specified, selected %s from sim start time' % cfg['grib_source'])
    else:
        print('Using GRIB source %s from %s' % (cfg['grib_source'], profile['template']))

    # build wrfpy_id and the visualization link
    job_id = 'wfc-%s-%s-%02d' % (sim_id, to_esmf(sim_start), fc_hours)
    sim_info['job_id']=job_id
    sim_info['visualization_link'] = conf['wrfxweb_url'] + '/#/view1?sim_id=' + job_id
    cfg['job_id']=job_id

    # place top-level domain
    cfg['domains']['1']['truelats'] = [ign_lat, ign_lat]
    cfg['domains']['1']['stand_lon'] = ign_lon
    cfg['domains']['1']['center_latlon'] = [ign_lat, ign_lon]

    # all templates have exactly one ignition
    domain = list(cfg['ignitions'].keys())[0]
    cfg['ignitions'][domain][0]['time_utc'] = ign_time_esmf
    # example:  "latlon" : [39.894264, -103.903222]
    cfg['ignitions'][domain][0]['latlon'] = [ign_lat, ign_lon]

    # switch on sending results to visualization server
    cfg['postproc']['shuttle'] = 'incremental'
    cfg['postproc']['description'] = sim_descr

    json.dump(cfg, open(json_path, 'w'),indent=1, separators=(',',':'))

    print('Job configuration %s:' % json_path)
    print(json.dumps(cfg, indent=4, separators=(',', ': ')))

    # drop a shell script that will run the file
    with open(run_script, 'w') as f:
        f.write('#!/usr/bin/env bash\n')
        #f.write('/usr/bin/env\n')
        f.write('export PYTHONPATH=src\n')
        f.write('cd ' + conf['wrfxpy_path'] + '\n')
        f.write('LOG=' + osp.abspath(log_path) + '\n')
        f.write('./forecast.sh ' + osp.abspath(json_path) + ' &> $LOG \n')

    # make it executable
    st = os.stat(run_script)
    os.chmod(run_script, st.st_mode | stat.S_IEXEC)

    # execute the fire forecast and reroute into the log file provided
    print('Running %s' % run_script)
    proc = Popen(run_script, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)
    print('Ready')
    

    return sim_info


def parse_error(state, line):
    """
    Find the tool that created the error in line and update state.

    :param line: the line that created the error
    :param state: the state dictionary containing state of each tool
    """
    tools = ['geogrid', 'ingest', 'ungrib', 'metgrid', 'real', 'wrf', 'output']
    for t in tools:
        if t in line.lower() or state[t] in ['waiting','running']:
            state[t] = 'failed'
            return


def parse_time(line):
    """
    All logging lines begin with a timestamp, parse it and return the datetime it represents.

    Example: 2016-04-14 14:50:33,325
    :param line: the log line containing time
    :return: native datetime
    """
    return datetime.strptime(line[:19], '%y-%m-%d %h:%M:%S')


def make_initial_state():
    """
    Create an initial state dictionary.
    """
    return { 'geogrid' : 'waiting',
             'ingest' : 'waiting',
             'ungrib' : 'waiting',
             'metgrid' : 'waiting',
             'real' : 'waiting',
             'wrf' : 'waiting',
             'output': 'waiting' }



def get_simulation_state(path):
    """
    Identify the state of the computation for each subcomponent
    from the output log. If the log does not exist, return default state.

    :param path: the path to the log file
    """
    state = make_initial_state()

    # for some reason the "with open(path) as f" started just quietly exiting
    # when the file does not exist...

    try:
        f = open(path)
        for line in f:
            if 'ERROR' in line:
                parse_error(state,line)
            if 'subprocess.CalledProcessError' in line:
                parse_error(state, line)
            if 'WRF completion detected' in line:
                state['wrf'] = 'complete'
            if 'running GEOGRID' in line:
                state['geogrid'] = 'running'
            elif 'GEOGRID complete' in line:
                state['geogrid'] = 'complete'
            elif 'retrieving GRIB files' in line:
                state['ingest'] = 'running'
            elif 'running UNGRIB' in line:
                state['ingest'] = 'complete'
                state['ungrib'] = 'running'
            elif 'UNGRIB complete' in line:
                state['ingest'] = 'complete'
                state['ungrib'] = 'complete'
            elif 'running METGRID' in line:
                state['metgrid'] = 'running'
            elif 'METGRID complete' in line:
                state['metgrid'] = 'complete'
            elif 'running REAL' in line:
                state['metgrid'] = 'complete'
                state['real'] = 'running'
            elif 'submitting WRF' in line:
                state['real'] = 'complete'
                state['wrf'] = 'submit'
            elif 'Detected rsl.error.0000' in line:
                state['wrf'] = 'running'
            elif 'SHUTTLE operations completed' in line:
                state['output'] = 'available'
            if 'Cancelled' in line:
                state['wrf'] = 'cancelled'
        f.close()
        if state['geogrid'] == 'failed' or \
           state['ungrib'] == 'failed':
            state['metgrid'] = 'failed'
            state['real'] = 'failed'
            state['wrf'] = 'failed'
            state['output'] = 'failed'
    except:
        print("Cannot open file %s" % path)
    return state
