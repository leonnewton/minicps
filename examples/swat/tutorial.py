"""
Use MiniCPS to simulate the first SWaT subprocess.

A state_db is used to represent the actual state of the system

graph_name functions are used to build networkx graphs representing the
topology you want to build.
"""

import time
import sys
import os
import argparse
sys.path.append(os.getcwd())

from minicps.devices import PLC, HMI, DumbSwitch, Histn, Attacker, Workstn, POXSwat
from minicps.links import EthLink
from minicps.topologies import TopoFromNxGraph
from minicps import constants as c

from constants import logger, L1_PLCS_IP, L1_NETMASK, PLCS_MAC, L2_HMI
from constants import OTHER_MACS, L3_PLANT_NETWORK
from constants import LIT_101

# used to separate different log sessions
logger.debug('----------'+time.asctime()+'----------')

from mininet.cli import CLI
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel

import networkx as nx
import matplotlib.pyplot as plt


def nxgraph_level1(attacker=False):
    """
    SWaT testbed L1 graph + L2 hmi + L3 histn and L3 workstn + optional
    attacker

    :attacker: add an additional Attacker device to the graph

    :returns: networkx graph
    """

    graph = nx.Graph()
    # graph = nx.DiGraph()

    graph.name = 'swat_level1'

    # Init switches
    s3 = DumbSwitch('s3')
    graph.add_node('s3', attr_dict=s3.get_params())

    # Create nodes and connect edges
    nodes = {}
    count = 0

    for i in range(1, 7):
        key = 'plc'+str(i)
        nodes[key] = PLC(key, L1_PLCS_IP[key], L1_NETMASK, PLCS_MAC[key])
        graph.add_node(key, attr_dict=nodes[key].get_params())
        link = EthLink(id=str(count), bw=30, delay=0, loss=0)
        graph.add_edge(key, 's3', attr_dict=link.get_params())
        count += 1
    assert len(graph) == 7, "plc nodes error"

    nodes['hmi'] = HMI('hmi', L2_HMI['hmi'], L1_NETMASK, OTHER_MACS['hmi'])
    graph.add_node('hmi', attr_dict=nodes['hmi'].get_params())
    link = EthLink(id=str(count), bw=30, delay=0, loss=0)
    graph.add_edge('hmi', 's3', attr_dict=link.get_params())
    count += 1

    nodes['histn'] = Histn('histn', L3_PLANT_NETWORK['histn'], L1_NETMASK,
            OTHER_MACS['histn'])
    graph.add_node('histn', attr_dict=nodes['histn'].get_params())
    link = EthLink(id=str(count), bw=30, delay=0, loss=0)
    graph.add_edge('histn', 's3', attr_dict=link.get_params())
    count += 1

    nodes['workstn'] = Histn('workstn', L3_PLANT_NETWORK['workstn'], L1_NETMASK,
            OTHER_MACS['workstn'])
    graph.add_node('workstn', attr_dict=nodes['workstn'].get_params())
    link = EthLink(id=str(count), bw=30, delay=0, loss=0)
    graph.add_edge('workstn', 's3', attr_dict=link.get_params())
    count += 1

    if attacker:
        nodes['attacker'] = Attacker('attacker', L1_PLCS_IP['attacker'], L1_NETMASK,
        OTHER_MACS['attacker'])
        graph.add_node('attacker', attr_dict=nodes['attacker'].get_params())
        link = EthLink(id=str(count), bw=30, delay=0, loss=0)
        graph.add_edge('attacker', 's3', attr_dict=link.get_params())
        assert len(graph) == 11, "attacker node error"

    return graph


def minicps_tutorial(net):
    """
    Settings used for tutorial

    :net: Mininet instance reference

    """
    # init the db
    os.system("python examples/swat/state_db.py")
    logger.debug("DB ready")

    net.start()

    plc1, plc2, plc3, hmi, s3 = net.get('plc1', 'plc2', 'plc3', 'hmi', 's3')

    os.system("mkdir -p examples/swat/err")
    # Init cpppo enip servers and run main loop
    os.system("python examples/swat/init_swat.py 2> examples/swat/err/init.err &")

    # This part launches the device simulation scripts.
    # This is where you can run your own device scripts, on the node of your
    # choice. Here plc1_0 script is running on the node plc1, and displays its
    # erros in plc1_0.err. This script only reads the state of the tank.
    #
    # You can try to comment plc1_0 line and uncomment plc1 line. This plc1
    # script is designed to take decisions according to the water level, to open
    # and close pumps.
    plc1_pid = plc1.cmd("python examples/swat/plc1_0.py 2> examples/swat/err/plc1_0.err &")
    # plc1_pid = plc1.cmd("python examples/swat/plc1.py 2> examples/swat/err/plc1.err &")

    plc2_pid = plc2.cmd("python examples/swat/plc2.py 2> examples/swat/err/plc2.err &")
    plc3_pid = plc3.cmd("python examples/swat/plc3.py 2> examples/swat/err/plc3.err &")
    hmi_pid = hmi.cmd("python examples/swat/hmi.py 2> examples/swat/err/hmi.err &")

    os.system("python examples/swat/physical_process.py 2> examples/swat/err/pp.err &")
    # Displays an image to monitor the physical process activity
    os.system("python examples/swat/image.py examples/swat/hmi/plc1.png 200 2> examples/swat/err/img.err &")
    CLI(net)

    net.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Minicps tutorial.')
    parser.add_argument('-l', '--levels', nargs=4, type=float, dest='levels',
                        default=argparse.SUPPRESS, metavar=('LL', 'L', 'H', 'HH'),
                        help='change the trigger level LL L H HH values.')
    args = parser.parse_args()
    if( len(args.levels) > 0 ):
        LIT_101['LL'] = args.levels[0]
        LIT_101['L'] = args.levels[1]
        LIT_101['H'] = args.levels[2]
        LIT_101['HH'] = args.levels[3]

    swat_graph = nxgraph_level1(attacker=True)
    topo = TopoFromNxGraph(swat_graph)
    controller = POXSwat
    net = Mininet(topo=topo, controller=controller, link=TCLink, listenPort=6634)

    minicps_tutorial(net)