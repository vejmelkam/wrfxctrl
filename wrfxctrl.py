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
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


from cluster import Cluster
from simulation import create_simulation, get_simulation_state
from utils import Dict, to_esmf, to_utc, load_profiles, load_simulations
from flask import Flask, render_template, request, redirect, make_response
import json
from datetime import datetime, timedelta
import pytz
import os
import stat
import os.path as osp
from subprocess import Popen
from functools import wraps, update_wrapper


# global objects tracking state
cluster = None
simulations = {}
profiles = None

#conf params
conf = json.load(open('etc/conf.json'))
root = conf['root']
host = conf['host']
debug = conf['debug'] in ['T' 'True' 't' 'true']
port=conf['port']
urls = {'submit': root+'/submit', 'welcome': root+'/start', 'overview': root+'/overview'}
print ( ' * Listening at %s' % urls['welcome'] )

app = Flask(__name__)

# lifted from: http://arusahni.net/blog/2014/03/flask-nocache.html
def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-Modified'] = datetime.now()
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response
        
    return update_wrapper(no_cache, view)


#@app.route(root)
@app.route(urls['welcome'])
@nocache
def welcome():
    return render_template('welcome.html', cluster=cluster, urls=urls)


@app.route(urls['submit'], methods=['GET', 'POST'])
def build():
    if request.method == 'GET':
        # it's a get so let's build a fire simulation
        return render_template('build.html', profiles=profiles.values(), urls=urls)
    elif request.method == 'POST':
        # it's a POST so initiate a simulation
        sim_cfg = request.form.copy()  # dictionary values set in the html  <select name="KEY" class="ui dropdown" id="KEY">
        print 'values returned by build page:'
        print  json.dumps(sim_cfg, indent=4, separators=(',', ': '))
        sim_cfg['profile'] = profiles[sim_cfg['profile']]
        sim_info = create_simulation(sim_cfg, conf,cluster)
        sim_id = sim_info['id']
        simulations[sim_id] = sim_info
        json.dump(sim_info, open('simulations/' + sim_id + '.json', 'w'), indent=4, separators=(',', ': '))
        return redirect("/monitor/%s" % sim_id)


@app.route("/monitor/<sim_id>")
@nocache
def monitor(sim_id=None):
    return render_template('monitor.html', sim = simulations.get(sim_id, None), urls=urls)


@app.route(urls['overview'])
@nocache
def overview():
    deadline = to_esmf(datetime.now() - timedelta(seconds=5))
    # only update stale & running simulations in overview
    for sim_id,sim in simulations.iteritems():
        if sim['state']['wrf'] != 'complete':
            last_upd = sim.get('last_updated', '2000-01-01_00:00:00')
            if last_upd < deadline:
                sim['state'] = get_simulation_state(sim['log_file'])
                sim['last_updated'] = to_esmf(datetime.now())
                json.dump(sim, open('simulations/' + sim_id + '.json', 'w'), indent=4, separators=(',', ': '))
    return render_template('overview.html', simulations = simulations, urls=urls)


# JSON access to state
@app.route("/retrieve_log/<sim_id>")
def retrieve_log(sim_id=None):
    sim_info = simulations.get(sim_id, None)
    if sim_info is None:
        return ""
    else:
        return open(sim_info['log_file']).read()


@app.route("/sim_info/<sim_id>")
def retrieve_sim_info(sim_id=None):
    sim_info = simulations.get(sim_id, {}).copy()
    return json.dumps(sim_info, indent=4, separators=(',', ': '))


@app.route("/get_state/<sim_id>")
def get_state(sim_id=None):
    sim_info = simulations.get(sim_id, None)
    if sim_info is None:
        return "{}"
    else:
        sim_state = None
        # always update during get_state()
        if sim_info['state']['wrf'] != 'completed':
            sim_state = get_simulation_state(sim_info['log_file'])
            sim_info['state'] = sim_state
            sim_info['last_updated'] = to_esmf(datetime.now())
            json.dump(sim_info, open('simulations/' + sim_id + '.json', 'w'))
        return json.dumps(sim_state)

@app.route("/remove_sim/<sim_id>")
def remove_sim(sim_id=None):
    if sim_id is not None:
        if sim_id in simulations:
            del simulations[sim_id]
            os.remove('simulations/' + sim_id + '.json')
            return "OK"
        else:
            return "NotFound"
    

@app.route("/all_sims")
def get_all_sims():
    return json.dumps(simulations, indent=4, separators=(',', ': '))


if __name__ == '__main__':
    profiles = load_profiles()
    cluster = Cluster(json.load(open('etc/cluster.json')))
    simulations = load_simulations()
    app.run(host=host,port=port,debug=debug)

