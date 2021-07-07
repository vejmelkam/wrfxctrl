from __future__ import absolute_import
from __future__ import print_function
from simulation import cancel_simulation, delete_simulation, delete_simulation_files, load_simulations, cleanup_sim_output, cleanup_sim_workspace
import json
import sys
import logging
from utils import load_sys_cfg

conf = load_sys_cfg()
sims_path = conf['sims_path']

def cleanup_delete(sim_id):
    simulations = load_simulations(sims_path)
    try:
        logging.info('Deleting simulation %s' % sim_id)
        sim_info = simulations[sim_id]
        delete_simulation(sim_info,conf)
    except KeyError:
        logging.error('Simulation %s not found.' % sim_id)
        delete_simulation_files(sim_id,conf) # rm any stray files

def cleanup_cancel(sim_id):
    simulations = load_simulations(sims_path)
    try:
        logging.info('Canceling simulation %s' % sim_id)
        sim_info = simulations[sim_id]
        cancel_simulation(sim_info,conf)
    except KeyError:
        logging.error('Simulation %s not found.' % sim_id)

def cleanup_output(sim_id):
    simulations = load_simulations(sims_path)
    try:
        logging.info('Cleanup output for %s' % sim_id)
        sim_info = simulations[sim_id]
        cleanup_sim_output(sim_info,conf)
    except KeyError:
        logging.error('Simulation %s not found.' % sim_id)

def cleanup_workspace(sim_id):
    simulations = load_simulations(sims_path)
    try:
        logging.info('Cleanup workspace for %s' % sim_id)
        sim_info = simulations[sim_id]
        cleanup_sim_workspace(sim_info,conf)
    except KeyError:
        logging.error('Simulation %s not found.' % sim_id)

def cleanup_list():
    simulations = load_simulations(sims_path)
    print('%-30s desc' % 'id') 
    print('-' * 40)
    for k in sorted(simulations):
        print('%-30s %s' % (k, simulations[k]['description']))

if __name__ == '__main__':

    if len(sys.argv) < 2:
        print('usage: %s [list|delete <name>' % sys.argv[0])
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if sys.argv[1] == 'delete':
        sim_id = sys.argv[2]
        cleanup_delete(sim_id)
    elif sys.argv[1] == 'cancel':
        sim_id=sys.argv[2]
        cleanup_cancel(sim_id)
    elif sys.argv[1] == 'output':
        sim_id=sys.argv[2]
        cleanup_output(sim_id)
    elif sys.argv[1] == 'workspace':
        sim_id=sys.argv[2]
        cleanup_workspace(sim_id)
    elif sys.argv[1] == 'list':
        cleanup_list()
    else:
        logging.error('command line not understood %s' % sys.argv)

