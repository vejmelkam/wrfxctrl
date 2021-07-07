from __future__ import absolute_import
import socket

class Cluster(object):
    """
    Represents the computing cluster available.
    """
    
    def __init__(self, cfg):
        self.hostname = socket.gethostname()
        self.nodes = cfg['nodes']
        self.ppn = cfg['ppn']
        # self.qsys = cfg['qsys']
        # FIXME
        self.free_nodes = self.nodes
